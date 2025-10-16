#!/usr/bin/env python3
"""
MongoDB Index Creation and Optimization Script

This script creates optimized indexes for the catalogue service MongoDB collections
to improve query performance and ensure data integrity.
"""

import asyncio
import logging
from typing import List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IndexManager:
    """Manages MongoDB indexes for the catalogue service."""
    
    def __init__(self, mongodb_url: str, database_name: str):
        """
        Initialize the index manager.
        
        Args:
            mongodb_url: MongoDB connection URL
            database_name: Name of the database
        """
        self.mongodb_url = mongodb_url
        self.database_name = database_name
        self.client = None
        self.db = None
    
    async def connect(self):
        """Establish connection to MongoDB."""
        try:
            self.client = AsyncIOMotorClient(self.mongodb_url)
            self.db = self.client[self.database_name]
            logger.info(f"Connected to MongoDB: {self.database_name}")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    async def disconnect(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    async def create_product_indexes(self) -> List[str]:
        """
        Create optimized indexes for the products collection.
        
        Returns:
            List of created index names
        """
        collection = self.db.products
        created_indexes = []
        
        try:
            # Text search index for name and description
            text_index = await collection.create_index([
                ("name", "text"),
                ("description", "text")
            ], name="text_search_idx")
            created_indexes.append(text_index)
            logger.info("Created text search index")
            
            # Compound index for category and active status
            category_active_index = await collection.create_index([
                ("category", 1),
                ("active", 1)
            ], name="category_active_idx")
            created_indexes.append(category_active_index)
            logger.info("Created category-active compound index")
            
            # Index for tags (multikey index)
            tags_index = await collection.create_index([
                ("tags", 1)
            ], name="tags_idx")
            created_indexes.append(tags_index)
            logger.info("Created tags index")
            
            # Compound index for featured and active products
            featured_active_index = await collection.create_index([
                ("featured", 1),
                ("active", 1)
            ], name="featured_active_idx")
            created_indexes.append(featured_active_index)
            logger.info("Created featured-active compound index")
            
            # Index for creation date (for recent products)
            created_at_index = await collection.create_index([
                ("created_at", -1)
            ], name="created_at_desc_idx")
            created_indexes.append(created_at_index)
            logger.info("Created created_at descending index")
            
            # Index for price (for price-based queries)
            price_index = await collection.create_index([
                ("price", 1)
            ], name="price_idx", sparse=True)  # Sparse because price is optional
            created_indexes.append(price_index)
            logger.info("Created price index (sparse)")
            
            # Compound index for inventory management
            inventory_index = await collection.create_index([
                ("active", 1),
                ("inventory_count", 1)
            ], name="active_inventory_idx", sparse=True)
            created_indexes.append(inventory_index)
            logger.info("Created active-inventory compound index")
            
            # Unique index for product names (to prevent duplicates)
            name_unique_index = await collection.create_index([
                ("name", 1)
            ], name="name_unique_idx", unique=True)
            created_indexes.append(name_unique_index)
            logger.info("Created unique name index")
            
            return created_indexes
            
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
            raise
    
    async def list_existing_indexes(self) -> List[Dict[str, Any]]:
        """
        List all existing indexes in the products collection.
        
        Returns:
            List of index information dictionaries
        """
        try:
            collection = self.db.products
            indexes = []
            
            async for index in collection.list_indexes():
                indexes.append(index)
            
            logger.info(f"Found {len(indexes)} existing indexes")
            return indexes
            
        except Exception as e:
            logger.error(f"Failed to list indexes: {e}")
            raise
    
    async def drop_index(self, index_name: str) -> bool:
        """
        Drop a specific index from the products collection.
        
        Args:
            index_name: Name of the index to drop
            
        Returns:
            True if successful, False otherwise
        """
        try:
            collection = self.db.products
            await collection.drop_index(index_name)
            logger.info(f"Dropped index: {index_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to drop index {index_name}: {e}")
            return False
    
    async def optimize_collection(self) -> Dict[str, Any]:
        """
        Optimize the products collection by analyzing and creating appropriate indexes.
        
        Returns:
            Dictionary with optimization results
        """
        try:
            collection = self.db.products
            
            # Get collection stats
            stats = await self.db.command("collStats", "products")
            
            # List existing indexes
            existing_indexes = await self.list_existing_indexes()
            existing_names = [idx.get('name', '') for idx in existing_indexes]
            
            # Create missing indexes
            created_indexes = []
            if 'text_search_idx' not in existing_names:
                created_indexes.extend(await self.create_product_indexes())
            else:
                logger.info("Indexes already exist, skipping creation")
            
            optimization_results = {
                'collection_stats': {
                    'document_count': stats.get('count', 0),
                    'storage_size': stats.get('storageSize', 0),
                    'index_count': stats.get('nindexes', 0),
                    'total_index_size': stats.get('totalIndexSize', 0)
                },
                'existing_indexes': len(existing_indexes),
                'created_indexes': len(created_indexes),
                'index_names': existing_names
            }
            
            logger.info("Collection optimization completed")
            return optimization_results
            
        except Exception as e:
            logger.error(f"Collection optimization failed: {e}")
            raise


async def main():
    """Main index creation function."""
    import os
    
    # Configuration
    mongodb_url = os.getenv('MONGODB_URL', 'mongodb://catalogue_user:catalogue_pass@localhost:27017/catalogue')
    database_name = os.getenv('MONGODB_DATABASE', 'catalogue')
    
    logger.info("Starting MongoDB index creation...")
    logger.info(f"MongoDB URL: {mongodb_url}")
    logger.info(f"Database: {database_name}")
    
    index_manager = IndexManager(mongodb_url, database_name)
    
    try:
        # Connect to database
        await index_manager.connect()
        
        # List existing indexes
        existing_indexes = await index_manager.list_existing_indexes()
        logger.info("Existing indexes:")
        for idx in existing_indexes:
            logger.info(f"  - {idx.get('name', 'unnamed')}: {idx.get('key', {})}")
        
        # Optimize collection (create indexes if needed)
        optimization_results = await index_manager.optimize_collection()
        
        logger.info("Optimization results:")
        logger.info(f"  Document count: {optimization_results['collection_stats']['document_count']}")
        logger.info(f"  Storage size: {optimization_results['collection_stats']['storage_size']} bytes")
        logger.info(f"  Index count: {optimization_results['collection_stats']['index_count']}")
        logger.info(f"  Total index size: {optimization_results['collection_stats']['total_index_size']} bytes")
        logger.info(f"  Created indexes: {optimization_results['created_indexes']}")
        
        logger.info("Index creation completed successfully!")
        
    except Exception as e:
        logger.error(f"Index creation failed: {e}")
        raise
    finally:
        await index_manager.disconnect()


if __name__ == "__main__":
    asyncio.run(main())