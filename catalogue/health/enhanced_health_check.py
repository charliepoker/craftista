"""
Enhanced health check implementation for the Catalogue Service.

This module provides comprehensive health checks for database connectivity,
circuit breaker status, and overall service health with detailed metrics.
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

from database.connection_manager import MongoDBConnectionManager
from database.circuit_breaker import get_all_circuit_breaker_metrics
from monitoring.structured_logger import get_database_metrics, health_logger


@dataclass
class ComponentHealth:
    """Health status for a service component."""
    name: str
    status: str  # "healthy", "degraded", "unhealthy"
    response_time_ms: float
    details: Dict[str, Any]
    error: Optional[str] = None


@dataclass
class ServiceHealth:
    """Overall service health status."""
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: str
    version: str
    uptime_seconds: float
    components: Dict[str, ComponentHealth]
    metrics: Dict[str, Any]


class EnhancedHealthChecker:
    """
    Enhanced health checker with comprehensive monitoring capabilities.
    """
    
    def __init__(self, connection_manager: MongoDBConnectionManager, 
                 service_version: str = "1.0.0"):
        self.connection_manager = connection_manager
        self.service_version = service_version
        self.start_time = time.time()
        
    async def check_database_health(self) -> ComponentHealth:
        """
        Check MongoDB database health with detailed metrics.
        
        Returns:
            ComponentHealth object with database status
        """
        start_time = time.time()
        
        try:
            # Perform database health check
            health_status = await self.connection_manager.health_check()
            response_time = (time.time() - start_time) * 1000
            
            # Determine component status based on response time and connection status
            if health_status["status"] == "healthy":
                if response_time < 100:  # < 100ms is excellent
                    status = "healthy"
                elif response_time < 500:  # < 500ms is acceptable
                    status = "healthy"
                else:  # > 500ms is degraded
                    status = "degraded"
            else:
                status = "unhealthy"
            
            component_health = ComponentHealth(
                name="mongodb",
                status=status,
                response_time_ms=round(response_time, 2),
                details={
                    "connected": health_status["database"]["connected"],
                    "database_response_time_ms": health_status["database"].get("response_time_ms"),
                    "pool_stats": health_status["database"].get("pool_stats", {}),
                    "connection_manager_status": "active" if self.connection_manager.is_connected else "inactive"
                }
            )
            
            # Log health check result
            health_logger.log_health_check(
                "mongodb", 
                status, 
                response_time / 1000,
                component_health.details
            )
            
            return component_health
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            component_health = ComponentHealth(
                name="mongodb",
                status="unhealthy",
                response_time_ms=round(response_time, 2),
                details={
                    "connected": False,
                    "connection_manager_status": "error"
                },
                error=str(e)
            )
            
            # Log health check failure
            health_logger.log_health_check_failure("mongodb", e, response_time / 1000)
            
            return component_health
    
    def check_circuit_breaker_health(self) -> ComponentHealth:
        """
        Check circuit breaker health and status.
        
        Returns:
            ComponentHealth object with circuit breaker status
        """
        start_time = time.time()
        
        try:
            # Get all circuit breaker metrics
            cb_metrics = get_all_circuit_breaker_metrics()
            response_time = (time.time() - start_time) * 1000
            
            # Determine overall circuit breaker health
            overall_status = "healthy"
            open_breakers = []
            degraded_breakers = []
            
            for name, metrics in cb_metrics.items():
                if metrics["state"] == "OPEN":
                    overall_status = "unhealthy"
                    open_breakers.append(name)
                elif metrics["state"] == "HALF_OPEN":
                    if overall_status == "healthy":
                        overall_status = "degraded"
                    degraded_breakers.append(name)
                elif metrics["failure_rate_percent"] > 50:
                    if overall_status == "healthy":
                        overall_status = "degraded"
                    degraded_breakers.append(name)
            
            component_health = ComponentHealth(
                name="circuit_breakers",
                status=overall_status,
                response_time_ms=round(response_time, 2),
                details={
                    "total_breakers": len(cb_metrics),
                    "open_breakers": open_breakers,
                    "degraded_breakers": degraded_breakers,
                    "breaker_metrics": cb_metrics
                }
            )
            
            # Log health check result
            health_logger.log_health_check(
                "circuit_breakers", 
                overall_status, 
                response_time / 1000,
                {
                    "total_breakers": len(cb_metrics),
                    "open_breakers": open_breakers,
                    "degraded_breakers": degraded_breakers
                }
            )
            
            return component_health
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            component_health = ComponentHealth(
                name="circuit_breakers",
                status="unhealthy",
                response_time_ms=round(response_time, 2),
                details={},
                error=str(e)
            )
            
            # Log health check failure
            health_logger.log_health_check_failure("circuit_breakers", e, response_time / 1000)
            
            return component_health
    
    def check_application_health(self) -> ComponentHealth:
        """
        Check application-level health metrics.
        
        Returns:
            ComponentHealth object with application status
        """
        start_time = time.time()
        
        try:
            # Get database operation metrics
            db_metrics = get_database_metrics()
            response_time = (time.time() - start_time) * 1000
            
            # Determine application health based on metrics
            status = "healthy"
            
            # Check error rate
            error_rate = db_metrics.get("error_rate", 0)
            if error_rate > 0.1:  # > 10% error rate
                status = "unhealthy"
            elif error_rate > 0.05:  # > 5% error rate
                status = "degraded"
            
            # Check average response time
            avg_duration = db_metrics.get("average_duration", 0)
            if avg_duration > 2.0:  # > 2 seconds average
                status = "unhealthy"
            elif avg_duration > 1.0:  # > 1 second average
                if status == "healthy":
                    status = "degraded"
            
            uptime = time.time() - self.start_time
            
            component_health = ComponentHealth(
                name="application",
                status=status,
                response_time_ms=round(response_time, 2),
                details={
                    "uptime_seconds": round(uptime, 2),
                    "database_metrics": db_metrics,
                    "memory_usage": "not_implemented",  # Could add psutil for memory monitoring
                    "cpu_usage": "not_implemented"      # Could add psutil for CPU monitoring
                }
            )
            
            # Log health check result
            health_logger.log_health_check(
                "application", 
                status, 
                response_time / 1000,
                {
                    "uptime_seconds": round(uptime, 2),
                    "error_rate": error_rate,
                    "avg_duration": avg_duration
                }
            )
            
            return component_health
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            component_health = ComponentHealth(
                name="application",
                status="unhealthy",
                response_time_ms=round(response_time, 2),
                details={},
                error=str(e)
            )
            
            # Log health check failure
            health_logger.log_health_check_failure("application", e, response_time / 1000)
            
            return component_health
    
    async def get_comprehensive_health(self) -> ServiceHealth:
        """
        Get comprehensive health status for the entire service.
        
        Returns:
            ServiceHealth object with overall status and component details
        """
        # Run all health checks concurrently
        db_health_task = asyncio.create_task(self.check_database_health())
        cb_health = self.check_circuit_breaker_health()
        app_health = self.check_application_health()
        
        # Wait for database health check to complete
        db_health = await db_health_task
        
        # Collect all component health statuses
        components = {
            "database": db_health,
            "circuit_breakers": cb_health,
            "application": app_health
        }
        
        # Determine overall service health
        overall_status = "healthy"
        for component in components.values():
            if component.status == "unhealthy":
                overall_status = "unhealthy"
                break
            elif component.status == "degraded" and overall_status == "healthy":
                overall_status = "degraded"
        
        # Get additional metrics
        uptime = time.time() - self.start_time
        db_metrics = get_database_metrics()
        cb_metrics = get_all_circuit_breaker_metrics()
        
        service_health = ServiceHealth(
            status=overall_status,
            timestamp=datetime.utcnow().isoformat() + "Z",
            version=self.service_version,
            uptime_seconds=round(uptime, 2),
            components=components,
            metrics={
                "database": db_metrics,
                "circuit_breakers": cb_metrics,
                "service": {
                    "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
                    "uptime_seconds": round(uptime, 2)
                }
            }
        )
        
        return service_health
    
    async def get_readiness_status(self) -> Dict[str, Any]:
        """
        Get readiness status (can the service handle requests?).
        
        Returns:
            Dictionary with readiness status
        """
        db_health = await self.check_database_health()
        cb_health = self.check_circuit_breaker_health()
        
        # Service is ready if database is accessible and no circuit breakers are open
        ready = (
            db_health.status in ["healthy", "degraded"] and
            cb_health.status in ["healthy", "degraded"]
        )
        
        return {
            "ready": ready,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "checks": {
                "database": {
                    "status": db_health.status,
                    "ready": db_health.status in ["healthy", "degraded"]
                },
                "circuit_breakers": {
                    "status": cb_health.status,
                    "ready": cb_health.status in ["healthy", "degraded"]
                }
            }
        }
    
    async def get_liveness_status(self) -> Dict[str, Any]:
        """
        Get liveness status (is the service alive?).
        
        Returns:
            Dictionary with liveness status
        """
        app_health = self.check_application_health()
        
        # Service is alive if application health check passes
        alive = app_health.status in ["healthy", "degraded"]
        
        return {
            "alive": alive,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "uptime_seconds": round(time.time() - self.start_time, 2),
            "version": self.service_version,
            "checks": {
                "application": {
                    "status": app_health.status,
                    "alive": alive
                }
            }
        }


def create_health_checker(connection_manager: MongoDBConnectionManager, 
                         version: str = "1.0.0") -> EnhancedHealthChecker:
    """
    Factory function to create an enhanced health checker.
    
    Args:
        connection_manager: MongoDB connection manager instance
        version: Service version string
        
    Returns:
        Configured EnhancedHealthChecker instance
    """
    return EnhancedHealthChecker(connection_manager, version)