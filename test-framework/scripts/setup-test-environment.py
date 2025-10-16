#!/usr/bin/env python3
"""
Test Environment Setup Script

This script sets up the comprehensive testing environment for the Craftista
microservices application, including database containers, test data, and
configuration validation.
"""

import os
import sys
import json
import yaml
import time
import subprocess
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import docker
from docker.errors import DockerException, NotFound, APIError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test-setup.log')
    ]
)
logger = logging.getLogger(__name__)

class TestEnvironmentSetup:
    """Manages the setup and teardown of the test environment."""
    
    def __init__(self, config_path: str):
        """Initialize the test environment setup."""
        self.config_path = Path(config_path)
        self.project_root = self.config_path.parent.parent
        self.config = self._load_config()
        self.docker_client = None
        self.containers = {}
        
    def _load_config(self) -> Dict[str, Any]:
        """Load the test configuration file."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            sys.exit(1)
    
    def _init_docker_client(self) -> None:
        """Initialize Docker client."""
        try:
            self.docker_client = docker.from_env()
            # Test Docker connection
            self.docker_client.ping()
            logger.info("Docker client initialized successfully")
        except DockerException as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            sys.exit(1)
    
    def check_prerequisites(self) -> bool:
        """Check if all prerequisites are met."""
        logger.info("Checking prerequisites...")
        
        # Check Docker
        try:
            subprocess.run(['docker', '--version'], 
                         check=True, capture_output=True)
            logger.info("✓ Docker is available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("✗ Docker is not available")
            return False
        
        # Check Docker Compose
        try:
            subprocess.run(['docker-compose', '--version'], 
                         check=True, capture_output=True)
            logger.info("✓ Docker Compose is available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("✗ Docker Compose is not available")
            return False
        
        # Check service-specific tools
        service_tools = {
            'catalogue': ['python3', 'pip3'],
            'voting': ['java', 'mvn'],
            'recommendation': ['go'],
            'frontend': ['node', 'npm']
        }
        
        for service, tools in service_tools.items():
            for tool in tools:
                try:
                    subprocess.run([tool, '--version'], 
                                 check=True, capture_output=True)
                    logger.info(f"✓ {tool} is available for {service} service")
                except (subprocess.CalledProcessError, FileNotFoundError):
                    logger.warning(f"✗ {tool} is not available for {service} service")
        
        return True
    
    def setup_databases(self, services: List[str]) -> bool:
        """Setup database containers for the specified services."""
        logger.info("Setting up database containers...")
        
        if not self.docker_client:
            self._init_docker_client()
        
        database_configs = self.config.get('databases', {})
        service_configs = self.config.get('services', {})
        
        # Determine which databases are needed
        required_databases = set()
        for service in services:
            if service in service_configs:
                db_type = service_configs[service].get('database')
                if db_type and db_type != 'none':
                    required_databases.add(db_type)
        
        logger.info(f"Required databases: {required_databases}")
        
        # Start database containers
        for db_type in required_databases:
            if db_type not in database_configs:
                logger.error(f"Database configuration not found for: {db_type}")
                return False
            
            if not self._start_database_container(db_type, database_configs[db_type]):
                return False
        
        return True
    
    def _start_database_container(self, db_type: str, db_config: Dict[str, Any]) -> bool:
        """Start a specific database container."""
        container_name = f"test-{db_type}"
        image = db_config['container_image']
        port = db_config['port']
        environment = db_config.get('environment', {})
        
        logger.info(f"Starting {db_type} container: {container_name}")
        
        try:
            # Check if container already exists
            try:
                existing_container = self.docker_client.containers.get(container_name)
                if existing_container.status == 'running':
                    logger.info(f"Container {container_name} is already running")
                    self.containers[db_type] = existing_container
                    return True
                else:
                    logger.info(f"Removing stopped container {container_name}")
                    existing_container.remove()
            except NotFound:
                pass  # Container doesn't exist, which is fine
            
            # Start new container
            container = self.docker_client.containers.run(
                image=image,
                name=container_name,
                ports={f'{port}/tcp': port},
                environment=environment,
                detach=True,
                remove=False
            )
            
            self.containers[db_type] = container
            logger.info(f"Started container {container_name}")
            
            # Wait for container to be ready
            if self._wait_for_database(db_type, db_config):
                logger.info(f"Database {db_type} is ready")
                return True
            else:
                logger.error(f"Database {db_type} failed to become ready")
                return False
                
        except APIError as e:
            logger.error(f"Failed to start {db_type} container: {e}")
            return False
    
    def _wait_for_database(self, db_type: str, db_config: Dict[str, Any], 
                          timeout: int = 60) -> bool:
        """Wait for database to be ready."""
        health_check = db_config.get('health_check', {})
        check_command = health_check.get('command')
        check_interval = health_check.get('interval', 5)
        max_retries = timeout // check_interval
        
        if not check_command:
            logger.warning(f"No health check command for {db_type}, waiting 10 seconds")
            time.sleep(10)
            return True
        
        container_name = f"test-{db_type}"
        
        for attempt in range(max_retries):
            try:
                # Execute health check command in container
                result = subprocess.run(
                    ['docker', 'exec', container_name] + check_command.split(),
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    return True
                    
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass
            
            logger.info(f"Waiting for {db_type} to be ready... (attempt {attempt + 1}/{max_retries})")
            time.sleep(check_interval)
        
        return False
    
    def setup_test_data(self, services: List[str]) -> bool:
        """Setup test data for the specified services."""
        logger.info("Setting up test data...")
        
        test_data_config = self.config.get('test_data', {})
        if not test_data_config.get('seed_data_enabled', False):
            logger.info("Test data seeding is disabled")
            return True
        
        fixtures_path = Path(test_data_config.get('fixtures_path', './test-framework/fixtures'))
        
        if not fixtures_path.exists():
            logger.warning(f"Fixtures directory not found: {fixtures_path}")
            return True
        
        # Load and apply fixtures for each service
        for service in services:
            service_fixtures_path = fixtures_path / service
            if service_fixtures_path.exists():
                logger.info(f"Loading test data for {service} service")
                self._load_service_fixtures(service, service_fixtures_path)
        
        return True
    
    def _load_service_fixtures(self, service: str, fixtures_path: Path) -> None:
        """Load test fixtures for a specific service."""
        # This would be implemented based on the specific service requirements
        # For now, just log the action
        logger.info(f"Loading fixtures from {fixtures_path} for {service}")
        
        # Example implementation for different services:
        if service == 'catalogue':
            self._load_mongodb_fixtures(fixtures_path)
        elif service == 'voting':
            self._load_postgresql_fixtures(fixtures_path)
        elif service == 'recommendation':
            self._load_redis_fixtures(fixtures_path)
    
    def _load_mongodb_fixtures(self, fixtures_path: Path) -> None:
        """Load MongoDB fixtures."""
        json_files = list(fixtures_path.glob('*.json'))
        for json_file in json_files:
            logger.info(f"Loading MongoDB fixture: {json_file}")
            # Implementation would use pymongo to load data
    
    def _load_postgresql_fixtures(self, fixtures_path: Path) -> None:
        """Load PostgreSQL fixtures."""
        sql_files = list(fixtures_path.glob('*.sql'))
        for sql_file in sql_files:
            logger.info(f"Loading PostgreSQL fixture: {sql_file}")
            # Implementation would execute SQL files
    
    def _load_redis_fixtures(self, fixtures_path: Path) -> None:
        """Load Redis fixtures."""
        json_files = list(fixtures_path.glob('*.json'))
        for json_file in json_files:
            logger.info(f"Loading Redis fixture: {json_file}")
            # Implementation would use redis-py to load data
    
    def validate_environment(self) -> bool:
        """Validate that the test environment is properly set up."""
        logger.info("Validating test environment...")
        
        # Check that all required containers are running
        for db_type, container in self.containers.items():
            try:
                container.reload()
                if container.status != 'running':
                    logger.error(f"Container for {db_type} is not running")
                    return False
                logger.info(f"✓ {db_type} container is running")
            except Exception as e:
                logger.error(f"Failed to check {db_type} container status: {e}")
                return False
        
        # Test database connections
        for db_type in self.containers.keys():
            if not self._test_database_connection(db_type):
                logger.error(f"Failed to connect to {db_type} database")
                return False
            logger.info(f"✓ {db_type} database connection successful")
        
        return True
    
    def _test_database_connection(self, db_type: str) -> bool:
        """Test connection to a specific database."""
        container_name = f"test-{db_type}"
        
        try:
            if db_type == 'mongodb':
                result = subprocess.run(
                    ['docker', 'exec', container_name, 'mongosh', '--eval', 'db.runCommand("ping")'],
                    capture_output=True, timeout=10
                )
            elif db_type == 'postgresql':
                result = subprocess.run(
                    ['docker', 'exec', container_name, 'pg_isready', '-U', 'testuser', '-d', 'testdb'],
                    capture_output=True, timeout=10
                )
            elif db_type == 'redis':
                result = subprocess.run(
                    ['docker', 'exec', container_name, 'redis-cli', 'ping'],
                    capture_output=True, timeout=10
                )
            else:
                return False
            
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            return False
    
    def cleanup_environment(self) -> None:
        """Clean up the test environment."""
        logger.info("Cleaning up test environment...")
        
        if not self.docker_client:
            return
        
        # Stop and remove containers
        for db_type, container in self.containers.items():
            try:
                logger.info(f"Stopping {db_type} container")
                container.stop(timeout=10)
                container.remove()
                logger.info(f"Removed {db_type} container")
            except Exception as e:
                logger.warning(f"Failed to cleanup {db_type} container: {e}")
        
        self.containers.clear()
    
    def generate_environment_info(self) -> Dict[str, Any]:
        """Generate information about the current test environment."""
        info = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'containers': {},
            'configuration': {
                'services': list(self.config.get('services', {}).keys()),
                'databases': list(self.config.get('databases', {}).keys())
            }
        }
        
        for db_type, container in self.containers.items():
            try:
                container.reload()
                info['containers'][db_type] = {
                    'name': container.name,
                    'status': container.status,
                    'image': container.image.tags[0] if container.image.tags else 'unknown',
                    'ports': container.ports
                }
            except Exception as e:
                info['containers'][db_type] = {'error': str(e)}
        
        return info


def main():
    """Main function to setup test environment."""
    parser = argparse.ArgumentParser(description='Setup test environment for Craftista microservices')
    parser.add_argument('--config', default='test-framework/config/test-config.yml',
                       help='Path to test configuration file')
    parser.add_argument('--services', default='all',
                       help='Comma-separated list of services or "all"')
    parser.add_argument('--cleanup', action='store_true',
                       help='Cleanup existing test environment')
    parser.add_argument('--validate-only', action='store_true',
                       help='Only validate the environment, do not setup')
    parser.add_argument('--info', action='store_true',
                       help='Generate environment information')
    
    args = parser.parse_args()
    
    # Initialize setup
    setup = TestEnvironmentSetup(args.config)
    
    try:
        if args.cleanup:
            setup.cleanup_environment()
            logger.info("Environment cleanup completed")
            return 0
        
        if args.info:
            info = setup.generate_environment_info()
            print(json.dumps(info, indent=2))
            return 0
        
        # Check prerequisites
        if not setup.check_prerequisites():
            logger.error("Prerequisites check failed")
            return 1
        
        if args.validate_only:
            if setup.validate_environment():
                logger.info("Environment validation successful")
                return 0
            else:
                logger.error("Environment validation failed")
                return 1
        
        # Parse services
        if args.services == 'all':
            services = list(setup.config.get('services', {}).keys())
        else:
            services = [s.strip() for s in args.services.split(',')]
        
        logger.info(f"Setting up environment for services: {services}")
        
        # Setup databases
        if not setup.setup_databases(services):
            logger.error("Database setup failed")
            return 1
        
        # Setup test data
        if not setup.setup_test_data(services):
            logger.error("Test data setup failed")
            return 1
        
        # Validate environment
        if not setup.validate_environment():
            logger.error("Environment validation failed")
            return 1
        
        logger.info("Test environment setup completed successfully")
        
        # Generate environment info
        info = setup.generate_environment_info()
        info_file = Path('test-environment-info.json')
        with open(info_file, 'w') as f:
            json.dump(info, f, indent=2)
        logger.info(f"Environment information saved to {info_file}")
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Setup interrupted by user")
        setup.cleanup_environment()
        return 1
    except Exception as e:
        logger.error(f"Unexpected error during setup: {e}")
        setup.cleanup_environment()
        return 1


if __name__ == '__main__':
    sys.exit(main())