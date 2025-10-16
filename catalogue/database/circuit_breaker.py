"""
Circuit Breaker Pattern Implementation for Database Operations

This module provides a circuit breaker implementation to prevent cascade failures
when database operations fail repeatedly. It includes fallback mechanisms and
monitoring capabilities.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Optional, Union
from dataclasses import dataclass
import threading

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5  # Number of failures before opening
    recovery_timeout: int = 60  # Seconds before trying half-open
    success_threshold: int = 3  # Successes needed to close from half-open
    timeout: int = 30  # Operation timeout in seconds


class CircuitBreakerException(Exception):
    """Raised when circuit breaker is open."""
    pass


class DatabaseCircuitBreaker:
    """
    Circuit breaker implementation for database operations.
    
    Prevents cascade failures by monitoring operation success/failure rates
    and temporarily blocking requests when failure threshold is exceeded.
    """
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.next_attempt_time: Optional[datetime] = None
        self._lock = threading.Lock()
        
        # Metrics for monitoring
        self.total_requests = 0
        self.total_failures = 0
        self.total_successes = 0
        self.state_changes = []
        
        logger.info(f"Circuit breaker '{name}' initialized with config: {config}")

    def _record_success(self) -> None:
        """Record a successful operation."""
        with self._lock:
            self.total_requests += 1
            self.total_successes += 1
            self.failure_count = 0
            
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self._transition_to_closed()
            
            logger.debug(f"Circuit breaker '{self.name}': Success recorded")

    def _record_failure(self) -> None:
        """Record a failed operation."""
        with self._lock:
            self.total_requests += 1
            self.total_failures += 1
            self.failure_count += 1
            self.success_count = 0
            self.last_failure_time = datetime.utcnow()
            
            if (self.state == CircuitBreakerState.CLOSED and 
                self.failure_count >= self.config.failure_threshold):
                self._transition_to_open()
            elif self.state == CircuitBreakerState.HALF_OPEN:
                self._transition_to_open()
            
            logger.warning(
                f"Circuit breaker '{self.name}': Failure recorded "
                f"(count: {self.failure_count})"
            )

    def _transition_to_open(self) -> None:
        """Transition circuit breaker to OPEN state."""
        self.state = CircuitBreakerState.OPEN
        self.next_attempt_time = (
            datetime.utcnow() + timedelta(seconds=self.config.recovery_timeout)
        )
        self._record_state_change("OPEN")
        logger.warning(
            f"Circuit breaker '{self.name}' opened. "
            f"Next attempt at {self.next_attempt_time}"
        )

    def _transition_to_half_open(self) -> None:
        """Transition circuit breaker to HALF_OPEN state."""
        self.state = CircuitBreakerState.HALF_OPEN
        self.success_count = 0
        self._record_state_change("HALF_OPEN")
        logger.info(f"Circuit breaker '{self.name}' half-opened for testing")

    def _transition_to_closed(self) -> None:
        """Transition circuit breaker to CLOSED state."""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.next_attempt_time = None
        self._record_state_change("CLOSED")
        logger.info(f"Circuit breaker '{self.name}' closed - normal operation resumed")

    def _record_state_change(self, new_state: str) -> None:
        """Record state change for monitoring."""
        self.state_changes.append({
            "timestamp": datetime.utcnow().isoformat(),
            "state": new_state,
            "failure_count": self.failure_count,
            "total_failures": self.total_failures
        })
        
        # Keep only last 100 state changes
        if len(self.state_changes) > 100:
            self.state_changes = self.state_changes[-100:]

    def _can_attempt(self) -> bool:
        """Check if an operation attempt is allowed."""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if (self.next_attempt_time and 
                datetime.utcnow() >= self.next_attempt_time):
                self._transition_to_half_open()
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return True
        return False

    async def call(self, operation: Callable, *args, **kwargs) -> Any:
        """
        Execute an operation through the circuit breaker.
        
        Args:
            operation: The async function to execute
            *args: Arguments for the operation
            **kwargs: Keyword arguments for the operation
            
        Returns:
            Result of the operation
            
        Raises:
            CircuitBreakerException: When circuit breaker is open
            Exception: Any exception from the operation
        """
        if not self._can_attempt():
            raise CircuitBreakerException(
                f"Circuit breaker '{self.name}' is OPEN. "
                f"Next attempt allowed at {self.next_attempt_time}"
            )

        try:
            # Execute operation with timeout
            result = await asyncio.wait_for(
                operation(*args, **kwargs),
                timeout=self.config.timeout
            )
            self._record_success()
            return result
            
        except asyncio.TimeoutError as e:
            self._record_failure()
            logger.error(f"Operation timeout in circuit breaker '{self.name}': {e}")
            raise
            
        except Exception as e:
            self._record_failure()
            logger.error(f"Operation failed in circuit breaker '{self.name}': {e}")
            raise

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get circuit breaker metrics for monitoring.
        
        Returns:
            Dictionary containing current metrics
        """
        with self._lock:
            failure_rate = (
                (self.total_failures / self.total_requests * 100)
                if self.total_requests > 0 else 0
            )
            
            return {
                "name": self.name,
                "state": self.state.value,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "total_requests": self.total_requests,
                "total_failures": self.total_failures,
                "total_successes": self.total_successes,
                "failure_rate_percent": round(failure_rate, 2),
                "last_failure_time": (
                    self.last_failure_time.isoformat() 
                    if self.last_failure_time else None
                ),
                "next_attempt_time": (
                    self.next_attempt_time.isoformat() 
                    if self.next_attempt_time else None
                ),
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "recovery_timeout": self.config.recovery_timeout,
                    "success_threshold": self.config.success_threshold,
                    "timeout": self.config.timeout
                },
                "recent_state_changes": self.state_changes[-10:]  # Last 10 changes
            }

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        with self._lock:
            self.state = CircuitBreakerState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            self.next_attempt_time = None
            logger.info(f"Circuit breaker '{self.name}' reset to initial state")


class DatabaseFallbackHandler:
    """
    Handles fallback mechanisms when database operations fail.
    """
    
    def __init__(self):
        self.cache = {}  # Simple in-memory cache for fallback data
        
    async def get_fallback_products(self) -> list:
        """
        Return fallback product data when database is unavailable.
        
        Returns:
            List of basic product information
        """
        logger.info("Returning fallback product data")
        return [
            {
                "id": "fallback-1",
                "name": "Basic Origami Paper",
                "description": "Standard origami paper for beginners",
                "image_url": "/static/images/origami/001-origami.png",
                "price": 9.99,
                "category": "paper",
                "active": True,
                "featured": False
            },
            {
                "id": "fallback-2", 
                "name": "Origami Instruction Book",
                "description": "Learn basic origami techniques",
                "image_url": "/static/images/origami/002-book.png",
                "price": 15.99,
                "category": "books",
                "active": True,
                "featured": True
            }
        ]
    
    async def get_fallback_product(self, product_id: str) -> Optional[dict]:
        """
        Return fallback data for a specific product.
        
        Args:
            product_id: ID of the requested product
            
        Returns:
            Product data or None if not available
        """
        fallback_products = await self.get_fallback_products()
        for product in fallback_products:
            if product["id"] == product_id:
                return product
        return None
    
    def cache_successful_response(self, key: str, data: Any, ttl: int = 300) -> None:
        """
        Cache successful responses for fallback use.
        
        Args:
            key: Cache key
            data: Data to cache
            ttl: Time to live in seconds
        """
        expiry = datetime.utcnow() + timedelta(seconds=ttl)
        self.cache[key] = {
            "data": data,
            "expiry": expiry
        }
        
        # Clean expired entries
        self._clean_expired_cache()
    
    def get_cached_response(self, key: str) -> Optional[Any]:
        """
        Get cached response if available and not expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached data or None
        """
        if key in self.cache:
            entry = self.cache[key]
            if datetime.utcnow() < entry["expiry"]:
                return entry["data"]
            else:
                del self.cache[key]
        return None
    
    def _clean_expired_cache(self) -> None:
        """Remove expired cache entries."""
        now = datetime.utcnow()
        expired_keys = [
            key for key, entry in self.cache.items()
            if now >= entry["expiry"]
        ]
        for key in expired_keys:
            del self.cache[key]


# Global circuit breaker instances
_circuit_breakers: Dict[str, DatabaseCircuitBreaker] = {}
_fallback_handler = DatabaseFallbackHandler()


def get_circuit_breaker(name: str, config: CircuitBreakerConfig = None) -> DatabaseCircuitBreaker:
    """
    Get or create a circuit breaker instance.
    
    Args:
        name: Circuit breaker name
        config: Configuration (uses default if not provided)
        
    Returns:
        Circuit breaker instance
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = DatabaseCircuitBreaker(name, config)
    return _circuit_breakers[name]


def get_fallback_handler() -> DatabaseFallbackHandler:
    """Get the global fallback handler instance."""
    return _fallback_handler


def get_all_circuit_breaker_metrics() -> Dict[str, Any]:
    """
    Get metrics for all circuit breakers.
    
    Returns:
        Dictionary with metrics for each circuit breaker
    """
    return {
        name: cb.get_metrics() 
        for name, cb in _circuit_breakers.items()
    }