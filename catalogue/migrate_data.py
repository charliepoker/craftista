#!/usr/bin/env python3
"""
Data migration script for Catalogue Service

This script migrates existing product data from JSON files to MongoDB,
ensuring data consistency and proper validation.
"""

import json
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient
from models.product import Product, ProductCreate
from repository.mongodb_repository import MongoDBProductRepository

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataMigrator:
    """Handles migration of product data from JSON to MongoDB."""
    
    def __init__(self, mongodb_url: str, database_name: str):
        """
        Initialize the data migrator.
        
        Args:
            mongodb_url: MongoDB connection URL
            database_name: Name of the database to migrate to
        """
        self.mongodb_url = mongodb_url
        self.database_name = database_name
        self.client = None
        self.repository = None
    
    async def connect(self):
        """Establish connection to MongoDB."""
        try:
            self.client = AsyncIOMotorClient(self.mongodb_url)
            database = self.client[self.database_name]
            self.repository = MongoDBProductRepository(database)
            logger.info(f"Connected to MongoDB: {self.database_name}")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    async def disconnect(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    def load_json_data(self, json_file_path: str) -> List[Dict[str, Any]]:
        """
        Load product data from JSON file.
        
        Args:
            json_file_path: Path to the JSON file containing product data
            
        Returns:
            List of product dictionaries
        """
        try:
            json_path = Path(json_file_path)
            if not json_path.exists():
                logger.error(f"JSON file not found: {json_file_path}")
                return []
            
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"Loaded {len(data)} products from {json_file_path}")
            return data
        except Exception as e:
            logger.error(f"Failed to load JSON data: {e}")
            return []
    
    def transform_product_data(self, json_product: Dict[str, Any]) -> ProductCreate:
        """
        Transform JSON product data to ProductCreate model.
        
        Args:
            json_product: Raw product data from JSON
            
        Returns:
            ProductCreate instance with validated data
        """
        try:
            # Map JSON fields to Product model fields
            product_data = {
                'name': json_product.get('name', '').strip(),
                'description': json_product.get('description', '').strip() or None,
                'image_url': json_product.get('image_url') or json_product.get('imageUrl'),
                'price': json_product.get('price'),
                'category': 'origami',  # Default category for existing products
                'tags': [],
                'attributes': {},
                'active': True,
                'featured': False,
                'inventory_count': 100  # Default inventory for migrated products
            }
            
            # Extract tags from name and description
            name_lower = product_data['name'].lower()
            if 'crane' in name_lower:
                product_data['tags'].extend(['crane', 'bird'])
            elif 'frog' in name_lower:
                product_data['tags'].extend(['frog', 'amphibian'])
            elif 'kangaroo' in name_lower:
                product_data['tags'].extend(['kangaroo', 'marsupial', 'australia'])
            elif 'camel' in name_lower:
                product_data['tags'].extend(['camel', 'desert'])
            elif 'butterfly' in name_lower:
                product_data['tags'].extend(['butterfly', 'insect', 'transformation'])
            
            # Add common tags
            product_data['tags'].extend(['paper', 'craft', 'decoration', 'origami'])
            
            # Set attributes based on product characteristics
            if 'crane' in name_lower or 'butterfly' in name_lower:
                product_data['attributes'] = {
                    'difficulty': 'intermediate',
                    'material': 'paper',
                    'size': 'medium'
                }
            elif 'frog' in name_lower:
                product_data['attributes'] = {
                    'difficulty': 'beginner',
                    'material': 'paper',
                    'size': 'small'
                }
            elif 'kangaroo' in name_lower:
                product_data['attributes'] = {
                    'difficulty': 'advanced',
                    'material': 'paper',
                    'size': 'large'
                }
                product_data['featured'] = True
            else:
                product_data['attributes'] = {
                    'difficulty': 'intermediate',
                    'material': 'paper',
                    'size': 'medium'
                }
            
            # Remove None values
            product_data = {k: v for k, v in product_data.items() if v is not None}
            
            return ProductCreate(**product_data)
            
        except Exception as e:
            logger.error(f"Failed to transform product data: {json_product.get('name', 'Unknown')}: {e}")
            raise
    
    async def migrate_products(self, json_file_path: str, dry_run: bool = False) -> int:
        """
        Migrate products from JSON file to MongoDB.
        
        Args:
            json_file_path: Path to JSON file containing product data
            dry_run: If True, validate data without inserting to database
            
        Returns:
            Number of products successfully migrated
        """
        if not self.repository:
            raise RuntimeError("Not connected to database. Call connect() first.")
        
        # Load JSON data
        json_products = self.load_json_data(json_file_path)
        if not json_products:
            logger.warning("No products to migrate")
            return 0
        
        migrated_count = 0
        errors = []
        
        for i, json_product in enumerate(json_products):
            try:
                # Transform data
                product_create = self.transform_product_data(json_product)
                
                if dry_run:
                    logger.info(f"[DRY RUN] Would migrate: {product_create.name}")
                else:
                    # Check if product already exists (by name)
                    existing_products = await self.repository.get_all_products()
                    existing_names = [p.name for p in existing_products]
                    
                    if product_create.name in existing_names:
                        logger.info(f"Product already exists, skipping: {product_create.name}")
                        continue
                    
                    # Create product in database
                    created_product = await self.repository.create_product(product_create)
                    logger.info(f"Migrated product: {created_product.name} (ID: {created_product.id})")
                
                migrated_count += 1
                
            except Exception as e:
                error_msg = f"Failed to migrate product {i+1}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue
        
        if errors:
            logger.warning(f"Migration completed with {len(errors)} errors:")
            for error in errors:
                logger.warning(f"  - {error}")
        
        logger.info(f"Migration completed: {migrated_count} products {'validated' if dry_run else 'migrated'}")
        return migrated_count
    
    async def verify_migration(self) -> Dict[str, Any]:
        """
        Verify the migration by checking database state.
        
        Returns:
            Dictionary with migration verification results
        """
        if not self.repository:
            raise RuntimeError("Not connected to database. Call connect() first.")
        
        try:
            # Get all products
            all_products = await self.repository.get_all_products()
            
            # Count by category
            categories = {}
            featured_count = 0
            active_count = 0
            
            for product in all_products:
                # Count categories
                category = product.category or 'uncategorized'
                categories[category] = categories.get(category, 0) + 1
                
                # Count featured and active
                if product.featured:
                    featured_count += 1
                if product.active:
                    active_count += 1
            
            verification_results = {
                'total_products': len(all_products),
                'active_products': active_count,
                'featured_products': featured_count,
                'categories': categories,
                'sample_products': [
                    {
                        'id': str(product.id),
                        'name': product.name,
                        'category': product.category,
                        'tags': product.tags[:3],  # First 3 tags
                        'featured': product.featured
                    }
                    for product in all_products[:5]  # First 5 products
                ]
            }
            
            logger.info("Migration verification completed")
            return verification_results
            
        except Exception as e:
            logger.error(f"Migration verification failed: {e}")
            raise


async def main():
    """Main migration function."""
    import os
    
    # Configuration
    mongodb_url = os.getenv('MONGODB_URL', 'mongodb://catalogue_user:catalogue_pass@localhost:27017/catalogue')
    database_name = os.getenv('MONGODB_DATABASE', 'catalogue')
    json_file_path = os.getenv('JSON_FILE_PATH', 'products.json')
    dry_run = os.getenv('DRY_RUN', 'false').lower() == 'true'
    
    logger.info("Starting data migration...")
    logger.info(f"MongoDB URL: {mongodb_url}")
    logger.info(f"Database: {database_name}")
    logger.info(f"JSON file: {json_file_path}")
    logger.info(f"Dry run: {dry_run}")
    
    migrator = DataMigrator(mongodb_url, database_name)
    
    try:
        # Connect to database
        await migrator.connect()
        
        # Run migration
        migrated_count = await migrator.migrate_products(json_file_path, dry_run=dry_run)
        
        if not dry_run and migrated_count > 0:
            # Verify migration
            verification = await migrator.verify_migration()
            logger.info("Migration verification results:")
            logger.info(f"  Total products: {verification['total_products']}")
            logger.info(f"  Active products: {verification['active_products']}")
            logger.info(f"  Featured products: {verification['featured_products']}")
            logger.info(f"  Categories: {verification['categories']}")
        
        logger.info("Migration completed successfully!")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        await migrator.disconnect()


if __name__ == "__main__":
    asyncio.run(main())