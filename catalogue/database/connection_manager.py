"""
MongoDB Connection Manager for Catalogue Service

This module provides a robust MongoDB connection manager with connection pooling,
retry logic, and health monitoring capabilities.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import os
from .circuit_breaker import get_circuit_breaker, get_fallback_handler, CircuitBreakerConfig

logger = logging.getLogger(__name__)


class DatabaseRetryManager:
    """Handles retry logic with exponential backoff for database operations."""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def execute_with_retry(self, operation, *args, **kwargs):
        """Execute an operation with retry logic and exponential backoff."""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return await operation(*args, **kwargs)
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(
                        f"Database operation failed (attempt {attempt + 1}/{self.max_retries + 1}). "
                        f"Retrying in {delay} seconds. Error: {str(e)}"
                    )
                    await asyncio.sleep(delay)
                    continue
                break

        raise DatabaseRetryExhaustedException(
            f"Failed after {self.max_retries} retries",
            last_exception
        )


class DatabaseRetryExhaustedException(Exception):
    """Raised when database retry attempts are exhausted."""
    
    def __init__(self, message: str, last_exception: Exception):
        super().__init__(message)
        self.last_exception = last_exception


class MongoDBConnectionManager:
    """
    MongoDB connection manager with connection pooling and health monitoring.
    
    Features:
    - Connection pooling with configurable parameters
    - Retry logic with exponential backoff
    - Health check capabilities
    - Graceful connection handling
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client: Optional[AsyncIOMotorClient] = None
        self.database = None
        self.retry_manager = DatabaseRetryManager(
            max_retries=config.get('retry_attempts', 3),
            base_delay=config.get('retry_delay', 1.0)
        )
        self._is_connected = False
        
        # Initialize circuit breaker
        cb_config = CircuitBreakerConfig(
            failure_threshold=config.get('circuit_breaker_failure_threshold', 5),
            recovery_timeout=config.get('circuit_breaker_recovery_timeout', 60),
            success_threshold=config.get('circuit_breaker_success_threshold', 3),
            timeout=config.get('circuit_breaker_timeout', 30)
        )
        self.circuit_breaker = get_circuit_breaker("mongodb_connection", cb_config)
        self.fallback_handler = get_fallback_handler()

    async def connect(self) -> None:
        """Establish connection to MongoDB with retry logic."""
        try:
            await self.retry_manager.execute_with_retry(self._connect)
            logger.info("Successfully connected to MongoDB")
        except DatabaseRetryExhaustedException as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    async def _connect(self) -> None:
        """Internal method to establish MongoDB connection."""
        mongodb_url = self.config.get('mongodb_url')
        if not mongodb_url:
            raise ValueError("MongoDB URL not provided in configuration")

        self.client = AsyncIOMotorClient(
            mongodb_url,
            maxPoolSize=self.config.get('max_pool_size', 10),
            minPoolSize=self.config.get('min_pool_size', 2),
            maxIdleTimeMS=self.config.get('max_idle_time_ms', 30000),
            serverSelectionTimeoutMS=self.config.get('server_selection_timeout_ms', 5000),
            connectTimeoutMS=self.config.get('connection_timeout_ms', 20000),
            retryWrites=True,
            retryReads=True
        )
        
        # Test the connection
        await self.client.admin.command('ping')
        
        database_name = self.config.get('database_name', 'catalogue')
        self.database = self.client[database_name]
        self._is_connected = True

    async def disconnect(self) -> None:
        """Close the MongoDB connection."""
        if self.client:
            self.client.close()
            self._is_connected = False
            logger.info("Disconnected from MongoDB")

    async def get_database(self):
        """Get the database instance with circuit breaker protection."""
        try:
            return await self.circuit_breaker.call(self._get_database_internal)
        except Exception as e:
            logger.error(f"Database access failed, using fallback: {e}")
            # Return None to indicate fallback should be used
            return None
    
    async def _get_database_internal(self):
        """Internal method to get database instance."""
        if not self._is_connected or not self.database:
            await self.connect()
        return self.database

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the MongoDB connection.
        
        Returns:
            Dict containing health status information
        """
        health_status = {
            "status": "unhealthy",
            "database": {
                "connected": False,
                "response_time_ms": None,
                "error": None
            },
            "timestamp": datetime.utcnow().isoformat()
        }

        try:
            if not self._is_connected or not self.client:
                await self.connect()

            start_time = datetime.utcnow()
            
            # Ping the database to check connectivity
            await self.client.admin.command('ping')
            
            end_time = datetime.utcnow()
            response_time = (end_time - start_time).total_seconds() * 1000

            # Get connection pool stats if available
            pool_stats = {}
            try:
                server_info = await self.client.server_info()
                pool_stats = {
                    "server_version": server_info.get("version", "unknown")
                }
            except Exception as e:
                logger.warning(f"Could not retrieve server info: {e}")

            health_status.update({
                "status": "healthy",
                "database": {
                    "connected": True,
                    "response_time_ms": round(response_time, 2),
                    "pool_stats": pool_stats,
                    "error": None
                }
            })

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health_status["database"]["error"] = str(e)

        return health_status

    @property
    def is_connected(self) -> bool:
        """Check if the connection is established."""
        return self._is_connected


def create_connection_manager() -> MongoDBConnectionManager:
    """
    Factory function to create a MongoDB connection manager with environment-based configuration.
    
    Returns:
        Configured MongoDBConnectionManager instance
    """
    config = {
        'mongodb_url': os.getenv('MONGODB_URL', 'mongodb://localhost:27017'),
        'database_name': os.getenv('MONGODB_DATABASE', 'catalogue'),
        'max_pool_size': int(os.getenv('MONGODB_MAX_POOL_SIZE', '10')),
        'min_pool_size': int(os.getenv('MONGODB_MIN_POOL_SIZE', '2')),
        'max_idle_time_ms': int(os.getenv('MONGODB_MAX_IDLE_TIME_MS', '30000')),
        'server_selection_timeout_ms': int(os.getenv('MONGODB_SERVER_SELECTION_TIMEOUT_MS', '5000')),
        'connection_timeout_ms': int(os.getenv('MONGODB_CONNECTION_TIMEOUT_MS', '20000')),
        'retry_attempts': int(os.getenv('MONGODB_RETRY_ATTEMPTS', '3')),
        'retry_delay': float(os.getenv('MONGODB_RETRY_DELAY', '1.0'))
    }
    
    return MongoDBConnectionManager(config)