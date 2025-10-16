"""
Health Check Module for Catalogue Service

This module provides comprehensive health checking capabilities including
database connectivity, system resources, and service dependencies.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional
from flask import jsonify, Response
from database.connection_manager import MongoDBConnectionManager
from config import get_config

logger = logging.getLogger(__name__)


class HealthChecker:
    """
    Comprehensive health checker for the catalogue service.
    
    Monitors:
    - Database connectivity
    - System resources
    - Configuration validity
    - Service dependencies
    """

    def __init__(self, db_manager: Optional[MongoDBConnectionManager] = None):
        self.db_manager = db_manager
        self.config = get_config()
        self.start_time = datetime.utcnow()

    async def check_health(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check.
        
        Returns:
            Dictionary containing health status and details
        """
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "catalogue",
            "version": self.config.app.version,
            "uptime": self._get_uptime(),
            "checks": {}
        }

        overall_healthy = True

        # Check database connectivity
        db_health = await self._check_database()
        health_status["checks"]["database"] = db_health
        if db_health["status"] != "healthy":
            overall_healthy = False

        # Check configuration
        config_health = self._check_configuration()
        health_status["checks"]["configuration"] = config_health
        if config_health["status"] != "healthy":
            overall_healthy = False

        # Check system resources
        system_health = self._check_system_resources()
        health_status["checks"]["system"] = system_health
        if system_health["status"] != "healthy":
            overall_healthy = False

        # Set overall status
        if not overall_healthy:
            health_status["status"] = "unhealthy"

        return health_status

    async def _check_database(self) -> Dict[str, Any]:
        """Check database connectivity and performance."""
        if not self.db_manager:
            return {
                "status": "unavailable",
                "message": "Database manager not initialized",
                "timestamp": datetime.utcnow().isoformat()
            }

        try:
            # Use the database manager's health check
            db_health = await self.db_manager.health_check()
            
            # Add additional checks specific to catalogue service
            if db_health["status"] == "healthy":
                # Test a simple query to ensure database is functional
                database = await self.db_manager.get_database()
                collections = await database.list_collection_names()
                
                db_health["database"]["collections_count"] = len(collections)
                db_health["database"]["collections"] = collections
                
                # Check if products collection exists and has data
                if "products" in collections:
                    products_collection = database.products
                    product_count = await products_collection.count_documents({})
                    db_health["database"]["products_count"] = product_count
                else:
                    db_health["database"]["products_count"] = 0
                    db_health["database"]["warning"] = "Products collection not found"

            return db_health

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    def _check_configuration(self) -> Dict[str, Any]:
        """Check configuration validity."""
        try:
            config_status = {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "details": {
                    "data_source": self.config.app.data_source,
                    "environment": self.config.app.environment,
                    "debug_mode": self.config.app.debug,
                    "database_configured": bool(self.config.database.mongodb_url)
                }
            }

            # Check for potential configuration issues
            warnings = []
            
            if self.config.app.environment == "production" and self.config.app.debug:
                warnings.append("Debug mode is enabled in production")
            
            if self.config.app.secret_key == "default-secret-key":
                warnings.append("Using default secret key")
            
            if not self.config.database.mongodb_url:
                warnings.append("MongoDB URL not configured")
                config_status["status"] = "unhealthy"

            if warnings:
                config_status["warnings"] = warnings

            return config_status

        except Exception as e:
            logger.error(f"Configuration health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource availability."""
        try:
            import psutil
            
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            system_status = {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "metrics": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_available_mb": memory.available // (1024 * 1024),
                    "disk_percent": disk.percent,
                    "disk_free_gb": disk.free // (1024 * 1024 * 1024)
                }
            }

            # Check for resource constraints
            warnings = []
            
            if cpu_percent > 90:
                warnings.append("High CPU usage")
                system_status["status"] = "degraded"
            
            if memory.percent > 90:
                warnings.append("High memory usage")
                system_status["status"] = "degraded"
            
            if disk.percent > 90:
                warnings.append("Low disk space")
                system_status["status"] = "degraded"

            if warnings:
                system_status["warnings"] = warnings

            return system_status

        except ImportError:
            # psutil not available, return basic status
            return {
                "status": "unknown",
                "message": "System monitoring not available (psutil not installed)",
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"System health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    def _get_uptime(self) -> str:
        """Get service uptime."""
        uptime_delta = datetime.utcnow() - self.start_time
        return str(uptime_delta)

    def get_readiness(self) -> Dict[str, Any]:
        """
        Check if the service is ready to accept requests.
        
        Returns:
            Dictionary containing readiness status
        """
        readiness = {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {}
        }

        ready = True

        # Check database connectivity (required for readiness)
        if self.db_manager:
            try:
                # Simple connectivity check
                asyncio.create_task(self.db_manager.health_check())
                readiness["checks"]["database"] = {"status": "ready"}
            except Exception as e:
                readiness["checks"]["database"] = {
                    "status": "not_ready",
                    "error": str(e)
                }
                ready = False
        else:
            readiness["checks"]["database"] = {
                "status": "not_ready",
                "error": "Database manager not initialized"
            }
            ready = False

        # Check configuration (required for readiness)
        if not self.config.database.mongodb_url:
            readiness["checks"]["configuration"] = {
                "status": "not_ready",
                "error": "Database not configured"
            }
            ready = False
        else:
            readiness["checks"]["configuration"] = {"status": "ready"}

        if not ready:
            readiness["status"] = "not_ready"

        return readiness

    def get_liveness(self) -> Dict[str, Any]:
        """
        Check if the service is alive and functioning.
        
        Returns:
            Dictionary containing liveness status
        """
        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": self._get_uptime(),
            "service": "catalogue",
            "version": self.config.app.version
        }


# Global health checker instance
_health_checker: Optional[HealthChecker] = None


def initialize_health_checker(db_manager: Optional[MongoDBConnectionManager] = None) -> None:
    """Initialize the global health checker."""
    global _health_checker
    _health_checker = HealthChecker(db_manager)


def get_health_checker() -> HealthChecker:
    """Get the global health checker instance."""
    if _health_checker is None:
        raise RuntimeError("Health checker not initialized")
    return _health_checker


# Flask route handlers
async def health_endpoint() -> Response:
    """Health check endpoint for Flask."""
    try:
        health_checker = get_health_checker()
        health_data = await health_checker.check_health()
        
        status_code = 200 if health_data["status"] == "healthy" else 503
        return jsonify(health_data), status_code
        
    except Exception as e:
        logger.error(f"Health check endpoint failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 503


def readiness_endpoint() -> Response:
    """Readiness check endpoint for Flask."""
    try:
        health_checker = get_health_checker()
        readiness_data = health_checker.get_readiness()
        
        status_code = 200 if readiness_data["status"] == "ready" else 503
        return jsonify(readiness_data), status_code
        
    except Exception as e:
        logger.error(f"Readiness check endpoint failed: {e}")
        return jsonify({
            "status": "not_ready",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 503


def liveness_endpoint() -> Response:
    """Liveness check endpoint for Flask."""
    try:
        health_checker = get_health_checker()
        liveness_data = health_checker.get_liveness()
        
        return jsonify(liveness_data), 200
        
    except Exception as e:
        logger.error(f"Liveness check endpoint failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 503