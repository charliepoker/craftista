#!/usr/bin/env python3
"""
MongoDB Migration Runner

This script orchestrates all MongoDB migration tasks including data migration,
index creation, and data validation for the catalogue service.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path to import modules
sys.path.append(str(Path(__file__).parent.parent))

from migrate_data import DataMigrator
from migrations.create_indexes import IndexManager
from migrations.validate_data import DataValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MigrationRunner:
    """Orchestrates all MongoDB migration tasks."""
    
    def __init__(self, mongodb_url: str, database_name: str):
        """
        Initialize the migration runner.
        
        Args:
            mongodb_url: MongoDB connection URL
            database_name: Name of the database
        """
        self.mongodb_url = mongodb_url
        self.database_name = database_name
        self.data_migrator = DataMigrator(mongodb_url, database_name)
        self.index_manager = IndexManager(mongodb_url, database_name)
        self.data_validator = DataValidator(mongodb_url, database_name)
    
    async def run_full_migration(self, json_file_path: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Run complete migration process including data migration, indexing, and validation.
        
        Args:
            json_file_path: Path to JSON file containing product data
            dry_run: If True, validate operations without making changes
            
        Returns:
            Dictionary with migration results
        """
        migration_results = {
            'data_migration': {},
            'index_creation': {},
            'data_validation': {},
            'success': False,
            'errors': []
        }
        
        try:
            logger.info("=== Starting Full MongoDB Migration ===")
            
            # Step 1: Data Migration
            logger.info("Step 1: Migrating data from JSON to MongoDB...")
            await self.data_migrator.connect()
            
            try:
                migrated_count = await self.data_migrator.migrate_products(json_file_path, dry_run=dry_run)
                migration_results['data_migration'] = {
                    'migrated_products': migrated_count,
                    'success': True
                }
                
                if not dry_run and migrated_count > 0:
                    verification = await self.data_migrator.verify_migration()
                    migration_results['data_migration']['verification'] = verification
                
            except Exception as e:
                migration_results['data_migration'] = {'success': False, 'error': str(e)}
                migration_results['errors'].append(f"Data migration failed: {e}")
                logger.error(f"Data migration failed: {e}")
            finally:
                await self.data_migrator.disconnect()
            
            # Step 2: Index Creation (only if data migration succeeded or dry_run)
            if migration_results['data_migration'].get('success', False) or dry_run:
                logger.info("Step 2: Creating MongoDB indexes...")
                await self.index_manager.connect()
                
                try:
                    optimization_results = await self.index_manager.optimize_collection()
                    migration_results['index_creation'] = {
                        'optimization_results': optimization_results,
                        'success': True
                    }
                    
                except Exception as e:
                    migration_results['index_creation'] = {'success': False, 'error': str(e)}
                    migration_results['errors'].append(f"Index creation failed: {e}")
                    logger.error(f"Index creation failed: {e}")
                finally:
                    await self.index_manager.disconnect()
            else:
                logger.warning("Skipping index creation due to data migration failure")
            
            # Step 3: Data Validation (always run)
            logger.info("Step 3: Validating migrated data...")
            await self.data_validator.connect()
            
            try:
                validation_report = await self.data_validator.generate_validation_report()
                migration_results['data_validation'] = {
                    'validation_report': validation_report,
                    'success': True
                }
                
                # Perform cleanup if there are issues and not in dry_run mode
                if not dry_run and validation_report.get('recommendations'):
                    cleanup_needed = any(
                        'Fix' in rec or 'Remove' in rec or 'Add' in rec 
                        for rec in validation_report.get('recommendations', [])
                    )
                    
                    if cleanup_needed:
                        logger.info("Performing data cleanup...")
                        cleanup_results = await self.data_validator.cleanup_invalid_data(dry_run=False)
                        migration_results['data_validation']['cleanup_results'] = cleanup_results
                
            except Exception as e:
                migration_results['data_validation'] = {'success': False, 'error': str(e)}
                migration_results['errors'].append(f"Data validation failed: {e}")
                logger.error(f"Data validation failed: {e}")
            finally:
                await self.data_validator.disconnect()
            
            # Determine overall success
            migration_results['success'] = (
                migration_results['data_migration'].get('success', False) and
                migration_results['index_creation'].get('success', False) and
                migration_results['data_validation'].get('success', False)
            )
            
            if migration_results['success']:
                logger.info("=== Full Migration Completed Successfully ===")
            else:
                logger.error("=== Migration Completed with Errors ===")
                for error in migration_results['errors']:
                    logger.error(f"  - {error}")
            
            return migration_results
            
        except Exception as e:
            logger.error(f"Migration runner failed: {e}")
            migration_results['errors'].append(f"Migration runner failed: {e}")
            migration_results['success'] = False
            return migration_results
    
    async def run_index_only(self) -> Dict[str, Any]:
        """
        Run only index creation and optimization.
        
        Returns:
            Dictionary with index creation results
        """
        try:
            logger.info("=== Running Index Creation Only ===")
            
            await self.index_manager.connect()
            optimization_results = await self.index_manager.optimize_collection()
            await self.index_manager.disconnect()
            
            logger.info("Index creation completed successfully")
            return {'success': True, 'results': optimization_results}
            
        except Exception as e:
            logger.error(f"Index creation failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def run_validation_only(self, cleanup: bool = False) -> Dict[str, Any]:
        """
        Run only data validation and optional cleanup.
        
        Args:
            cleanup: If True, perform data cleanup after validation
            
        Returns:
            Dictionary with validation results
        """
        try:
            logger.info("=== Running Data Validation Only ===")
            
            await self.data_validator.connect()
            
            validation_report = await self.data_validator.generate_validation_report()
            results = {'validation_report': validation_report}
            
            if cleanup:
                logger.info("Performing data cleanup...")
                cleanup_results = await self.data_validator.cleanup_invalid_data(dry_run=False)
                results['cleanup_results'] = cleanup_results
            
            await self.data_validator.disconnect()
            
            logger.info("Data validation completed successfully")
            return {'success': True, 'results': results}
            
        except Exception as e:
            logger.error(f"Data validation failed: {e}")
            return {'success': False, 'error': str(e)}


async def main():
    """Main migration runner function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='MongoDB Migration Runner for Catalogue Service')
    parser.add_argument('--mode', choices=['full', 'data', 'index', 'validate'], 
                       default='full', help='Migration mode to run')
    parser.add_argument('--json-file', default='products.json', 
                       help='Path to JSON file for data migration')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Run in dry-run mode (no actual changes)')
    parser.add_argument('--cleanup', action='store_true', 
                       help='Perform data cleanup during validation')
    parser.add_argument('--mongodb-url', 
                       default=os.getenv('MONGODB_URL', 'mongodb://catalogue_user:catalogue_pass@localhost:27017/catalogue'),
                       help='MongoDB connection URL')
    parser.add_argument('--database', 
                       default=os.getenv('MONGODB_DATABASE', 'catalogue'),
                       help='MongoDB database name')
    
    args = parser.parse_args()
    
    logger.info(f"MongoDB Migration Runner - Mode: {args.mode}")
    logger.info(f"MongoDB URL: {args.mongodb_url}")
    logger.info(f"Database: {args.database}")
    logger.info(f"Dry run: {args.dry_run}")
    
    runner = MigrationRunner(args.mongodb_url, args.database)
    
    try:
        if args.mode == 'full':
            results = await runner.run_full_migration(args.json_file, dry_run=args.dry_run)
        elif args.mode == 'data':
            await runner.data_migrator.connect()
            migrated_count = await runner.data_migrator.migrate_products(args.json_file, dry_run=args.dry_run)
            await runner.data_migrator.disconnect()
            results = {'success': True, 'migrated_products': migrated_count}
        elif args.mode == 'index':
            results = await runner.run_index_only()
        elif args.mode == 'validate':
            results = await runner.run_validation_only(cleanup=args.cleanup)
        
        if results.get('success', False):
            logger.info("Migration completed successfully!")
            sys.exit(0)
        else:
            logger.error("Migration failed!")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Migration runner failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())