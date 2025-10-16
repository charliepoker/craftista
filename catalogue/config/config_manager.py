"""
Configuration Manager for Catalogue Service

This module provides centralized configuration management with environment variable
support, validation, and fail-fast mechanisms.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "catalogue"
    max_pool_size: int = 10
    min_pool_size: int = 2
    max_idle_time_ms: int = 30000
    server_selection_timeout_ms: int = 5000
    connection_timeout_ms: int = 20000
    retry_attempts: int = 3
    retry_delay: float = 1.0


@dataclass
class AppConfig:
    """Application configuration settings."""
    version: str = "1.0.0"
    debug: bool = False
    environment: str = "production"
    data_source: str = "mongodb"  # "json" or "mongodb"
    secret_key: str = "default-secret-key"
    cors_origins: list = field(default_factory=lambda: ["http://localhost:3000"])


@dataclass
class HealthConfig:
    """Health check configuration settings."""
    enabled: bool = True
    interval: int = 30


@dataclass
class LoggingConfig:
    """Logging configuration settings."""
    level: str = "INFO"
    format: str = "json"


@dataclass
class PerformanceConfig:
    """Performance configuration settings."""
    max_content_length: int = 16777216  # 16MB
    request_timeout: int = 30


@dataclass
class Config:
    """Main configuration class containing all service settings."""
    app: AppConfig = field(default_factory=AppConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    health: HealthConfig = field(default_factory=HealthConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)


class ConfigManager:
    """
    Configuration manager that loads settings from multiple sources:
    1. Environment variables (highest priority)
    2. .env file
    3. config.json file (legacy support)
    4. Default values (lowest priority)
    """

    def __init__(self, config_file: Optional[str] = None, env_file: Optional[str] = None):
        self.config_file = config_file or "config.json"
        self.env_file = env_file or ".env"
        self._config: Optional[Config] = None
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from all sources."""
        try:
            # Load .env file if it exists
            self._load_env_file()
            
            # Create config with environment variables and defaults
            self._config = Config(
                app=AppConfig(
                    version=self._get_env("APP_VERSION", "1.0.0"),
                    debug=self._get_env_bool("FLASK_DEBUG", False),
                    environment=self._get_env("FLASK_ENV", "production"),
                    data_source=self._get_env("DATA_SOURCE", "mongodb"),
                    secret_key=self._get_env("SECRET_KEY", "default-secret-key"),
                    cors_origins=self._get_env_list("CORS_ORIGINS", ["http://localhost:3000"])
                ),
                database=DatabaseConfig(
                    mongodb_url=self._get_env("MONGODB_URL", "mongodb://localhost:27017"),
                    database_name=self._get_env("MONGODB_DATABASE", "catalogue"),
                    max_pool_size=self._get_env_int("MONGODB_MAX_POOL_SIZE", 10),
                    min_pool_size=self._get_env_int("MONGODB_MIN_POOL_SIZE", 2),
                    max_idle_time_ms=self._get_env_int("MONGODB_MAX_IDLE_TIME_MS", 30000),
                    server_selection_timeout_ms=self._get_env_int("MONGODB_SERVER_SELECTION_TIMEOUT_MS", 5000),
                    connection_timeout_ms=self._get_env_int("MONGODB_CONNECTION_TIMEOUT_MS", 20000),
                    retry_attempts=self._get_env_int("MONGODB_RETRY_ATTEMPTS", 3),
                    retry_delay=self._get_env_float("MONGODB_RETRY_DELAY", 1.0)
                ),
                health=HealthConfig(
                    enabled=self._get_env_bool("HEALTH_CHECK_ENABLED", True),
                    interval=self._get_env_int("HEALTH_CHECK_INTERVAL", 30)
                ),
                logging=LoggingConfig(
                    level=self._get_env("LOG_LEVEL", "INFO"),
                    format=self._get_env("LOG_FORMAT", "json")
                ),
                performance=PerformanceConfig(
                    max_content_length=self._get_env_int("MAX_CONTENT_LENGTH", 16777216),
                    request_timeout=self._get_env_int("REQUEST_TIMEOUT", 30)
                )
            )

            # Load legacy config.json for backward compatibility
            self._load_legacy_config()
            
            # Validate configuration
            self._validate_config()
            
            logger.info("Configuration loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise ConfigurationError(f"Configuration loading failed: {e}")

    def _load_env_file(self) -> None:
        """Load environment variables from .env file."""
        env_path = Path(self.env_file)
        if env_path.exists():
            try:
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            # Only set if not already in environment
                            if key not in os.environ:
                                os.environ[key] = value
                logger.info(f"Loaded environment variables from {self.env_file}")
            except Exception as e:
                logger.warning(f"Failed to load .env file: {e}")

    def _load_legacy_config(self) -> None:
        """Load legacy config.json file for backward compatibility."""
        config_path = Path(self.config_file)
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    legacy_config = json.load(f)
                
                # Update config with legacy values if not set by environment
                if "app_version" in legacy_config and not os.getenv("APP_VERSION"):
                    self._config.app.version = legacy_config["app_version"]
                
                if "data_source" in legacy_config and not os.getenv("DATA_SOURCE"):
                    self._config.app.data_source = legacy_config["data_source"]
                
                # Legacy database configuration
                if not os.getenv("MONGODB_URL"):
                    if all(key in legacy_config for key in ["db_host", "db_name", "db_user", "db_password"]):
                        # Convert PostgreSQL config to MongoDB URL format
                        # This is for backward compatibility - in practice, you'd migrate the data
                        logger.warning("Legacy PostgreSQL configuration detected. Consider migrating to MongoDB.")
                
                logger.info("Legacy configuration loaded and merged")
                
            except Exception as e:
                logger.warning(f"Failed to load legacy config file: {e}")

    def _validate_config(self) -> None:
        """Validate the loaded configuration."""
        errors = []

        # Validate required fields
        if not self._config.app.secret_key or self._config.app.secret_key == "default-secret-key":
            if self._config.app.environment == "production":
                errors.append("SECRET_KEY must be set in production environment")

        if not self._config.database.mongodb_url:
            errors.append("MONGODB_URL is required")

        # Validate numeric ranges
        if self._config.database.max_pool_size <= 0:
            errors.append("MONGODB_MAX_POOL_SIZE must be greater than 0")

        if self._config.database.min_pool_size < 0:
            errors.append("MONGODB_MIN_POOL_SIZE must be non-negative")

        if self._config.database.min_pool_size > self._config.database.max_pool_size:
            errors.append("MONGODB_MIN_POOL_SIZE cannot be greater than MONGODB_MAX_POOL_SIZE")

        # Validate data source
        if self._config.app.data_source not in ["json", "mongodb"]:
            errors.append("DATA_SOURCE must be either 'json' or 'mongodb'")

        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors)
            raise ConfigurationError(error_msg)

    def _get_env(self, key: str, default: str) -> str:
        """Get environment variable as string."""
        return os.getenv(key, default)

    def _get_env_bool(self, key: str, default: bool) -> bool:
        """Get environment variable as boolean."""
        value = os.getenv(key)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes", "on")

    def _get_env_int(self, key: str, default: int) -> int:
        """Get environment variable as integer."""
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            logger.warning(f"Invalid integer value for {key}: {value}, using default: {default}")
            return default

    def _get_env_float(self, key: str, default: float) -> float:
        """Get environment variable as float."""
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return float(value)
        except ValueError:
            logger.warning(f"Invalid float value for {key}: {value}, using default: {default}")
            return default

    def _get_env_list(self, key: str, default: list) -> list:
        """Get environment variable as list (comma-separated)."""
        value = os.getenv(key)
        if value is None:
            return default
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def config(self) -> Config:
        """Get the current configuration."""
        if self._config is None:
            raise ConfigurationError("Configuration not loaded")
        return self._config

    def reload(self) -> None:
        """Reload configuration from all sources."""
        logger.info("Reloading configuration...")
        self._load_config()

    def get_database_config_dict(self) -> Dict[str, Any]:
        """Get database configuration as dictionary for connection manager."""
        db_config = self._config.database
        return {
            'mongodb_url': db_config.mongodb_url,
            'database_name': db_config.database_name,
            'max_pool_size': db_config.max_pool_size,
            'min_pool_size': db_config.min_pool_size,
            'max_idle_time_ms': db_config.max_idle_time_ms,
            'server_selection_timeout_ms': db_config.server_selection_timeout_ms,
            'connection_timeout_ms': db_config.connection_timeout_ms,
            'retry_attempts': db_config.retry_attempts,
            'retry_delay': db_config.retry_delay
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'app': {
                'version': self._config.app.version,
                'debug': self._config.app.debug,
                'environment': self._config.app.environment,
                'data_source': self._config.app.data_source,
                'cors_origins': self._config.app.cors_origins
            },
            'database': {
                'mongodb_url': self._config.database.mongodb_url,
                'database_name': self._config.database.database_name,
                'max_pool_size': self._config.database.max_pool_size,
                'min_pool_size': self._config.database.min_pool_size,
                'retry_attempts': self._config.database.retry_attempts
            },
            'health': {
                'enabled': self._config.health.enabled,
                'interval': self._config.health.interval
            },
            'logging': {
                'level': self._config.logging.level,
                'format': self._config.logging.format
            },
            'performance': {
                'max_content_length': self._config.performance.max_content_length,
                'request_timeout': self._config.performance.request_timeout
            }
        }


class ConfigurationError(Exception):
    """Raised when configuration loading or validation fails."""
    pass


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config() -> Config:
    """Get the current configuration."""
    return get_config_manager().config