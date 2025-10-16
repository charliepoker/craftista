#!/usr/bin/env python3
"""
MongoDB Data Validation and Cleanup Script

This script validates existing data in MongoDB collections and performs
cleanup operations to ensure data integrity and consistency.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from models.product import Product

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataValidator:
    """Validates and cleans MongoDB data for the catalogue service."""
    
    def __init__(self, mongodb_url: str, database_name: str):
        """
        Initialize the data validator.
        
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
    
    async def validate_product_schema(self) -> Dict[str, Any]:
        """
        Validate that all products conform to the expected schema.
        
        Returns:
            Dictionary with validation results
        """
        collection = self.db.products
        validation_results = {
            'total_documents': 0,
            'valid_documents': 0,
            'invalid_documents': 0,
            'validation_errors': [],
            'missing_fields': {},
            'invalid_field_types': {}
        }
        
        try:
            async for doc in collection.find():
                validation_results['total_documents'] += 1
                
                try:
                    # Try to create Product model from document
                    # This will validate the schema
                    product = Product(**doc)
                    validation_results['valid_documents'] += 1
                    
                except Exception as e:
                    validation_results['invalid_documents'] += 1
                    error_info = {
                        'document_id': str(doc.get('_id', 'unknown')),
                        'error': str(e),
                        'document_name': doc.get('name', 'unnamed')
                    }
                    validation_results['validation_errors'].append(error_info)
                    
                    # Analyze specific validation issues
                    self._analyze_validation_error(doc, str(e), validation_results)
            
            logger.info(f"Schema validation completed: {validation_results['valid_documents']}/{validation_results['total_documents']} valid")
            return validation_results
            
        except Exception as e:
            logger.error(f"Schema validation failed: {e}")
            raise
    
    def _analyze_validation_error(self, doc: Dict[str, Any], error: str, results: Dict[str, Any]):
        """Analyze validation errors to identify common issues."""
        # Check for missing required fields
        required_fields = ['name']
        for field in required_fields:
            if field not in doc or not doc[field]:
                if field not in results['missing_fields']:
                    results['missing_fields'][field] = 0
                results['missing_fields'][field] += 1
        
        # Check for invalid field types
        if 'price' in doc and doc['price'] is not None:
            if not isinstance(doc['price'], (int, float)):
                if 'price' not in results['invalid_field_types']:
                    results['invalid_field_types']['price'] = 0
                results['invalid_field_types']['price'] += 1
        
        if 'active' in doc and not isinstance(doc['active'], bool):
            if 'active' not in results['invalid_field_types']:
                results['invalid_field_types']['active'] = 0
            results['invalid_field_types']['active'] += 1
    
    async def validate_data_integrity(self) -> Dict[str, Any]:
        """
        Validate data integrity constraints and business rules.
        
        Returns:
            Dictionary with integrity validation results
        """
        collection = self.db.products
        integrity_results = {
            'duplicate_names': [],
            'invalid_prices': [],
            'missing_descriptions': [],
            'invalid_inventory': [],
            'orphaned_images': [],
            'inconsistent_tags': []
        }
        
        try:
            # Check for duplicate product names
            pipeline = [
                {"$group": {"_id": "$name", "count": {"$sum": 1}, "docs": {"$push": "$$ROOT"}}},
                {"$match": {"count": {"$gt": 1}}}
            ]
            
            async for result in collection.aggregate(pipeline):
                integrity_results['duplicate_names'].append({
                    'name': result['_id'],
                    'count': result['count'],
                    'document_ids': [str(doc['_id']) for doc in result['docs']]
                })
            
            # Check for invalid prices (negative values)
            async for doc in collection.find({"price": {"$lt": 0}}):
                integrity_results['invalid_prices'].append({
                    'document_id': str(doc['_id']),
                    'name': doc.get('name', 'unnamed'),
                    'price': doc.get('price')
                })
            
            # Check for products without descriptions
            async for doc in collection.find({"$or": [{"description": None}, {"description": ""}]}):
                integrity_results['missing_descriptions'].append({
                    'document_id': str(doc['_id']),
                    'name': doc.get('name', 'unnamed')
                })
            
            # Check for invalid inventory counts
            async for doc in collection.find({"inventory_count": {"$lt": 0}}):
                integrity_results['invalid_inventory'].append({
                    'document_id': str(doc['_id']),
                    'name': doc.get('name', 'unnamed'),
                    'inventory_count': doc.get('inventory_count')
                })
            
            # Check for inconsistent tag formats
            async for doc in collection.find({"tags": {"$exists": True}}):
                tags = doc.get('tags', [])
                if not isinstance(tags, list):
                    integrity_results['inconsistent_tags'].append({
                        'document_id': str(doc['_id']),
                        'name': doc.get('name', 'unnamed'),
                        'tags_type': type(tags).__name__
                    })
                elif any(not isinstance(tag, str) for tag in tags):
                    integrity_results['inconsistent_tags'].append({
                        'document_id': str(doc['_id']),
                        'name': doc.get('name', 'unnamed'),
                        'issue': 'non-string tags found'
                    })
            
            logger.info("Data integrity validation completed")
            return integrity_results
            
        except Exception as e:
            logger.error(f"Data integrity validation failed: {e}")
            raise
    
    async def cleanup_invalid_data(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Clean up invalid data based on validation results.
        
        Args:
            dry_run: If True, only report what would be cleaned without making changes
            
        Returns:
            Dictionary with cleanup results
        """
        collection = self.db.products
        cleanup_results = {
            'fixed_prices': 0,
            'added_descriptions': 0,
            'fixed_inventory': 0,
            'normalized_tags': 0,
            'removed_duplicates': 0
        }
        
        try:
            # Fix negative prices (set to None)
            if dry_run:
                count = await collection.count_documents({"price": {"$lt": 0}})
                logger.info(f"[DRY RUN] Would fix {count} negative prices")
            else:
                result = await collection.update_many(
                    {"price": {"$lt": 0}},
                    {"$set": {"price": None}}
                )
                cleanup_results['fixed_prices'] = result.modified_count
                logger.info(f"Fixed {result.modified_count} negative prices")
            
            # Add default descriptions for products without them
            if dry_run:
                count = await collection.count_documents({"$or": [{"description": None}, {"description": ""}]})
                logger.info(f"[DRY RUN] Would add descriptions to {count} products")
            else:
                async for doc in collection.find({"$or": [{"description": None}, {"description": ""}]}):
                    default_description = f"Beautiful {doc.get('name', 'origami')} crafted with precision and care."
                    await collection.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {"description": default_description}}
                    )
                    cleanup_results['added_descriptions'] += 1
                logger.info(f"Added descriptions to {cleanup_results['added_descriptions']} products")
            
            # Fix negative inventory counts
            if dry_run:
                count = await collection.count_documents({"inventory_count": {"$lt": 0}})
                logger.info(f"[DRY RUN] Would fix {count} negative inventory counts")
            else:
                result = await collection.update_many(
                    {"inventory_count": {"$lt": 0}},
                    {"$set": {"inventory_count": 0}}
                )
                cleanup_results['fixed_inventory'] = result.modified_count
                logger.info(f"Fixed {result.modified_count} negative inventory counts")
            
            # Normalize tags (ensure they are arrays of strings)
            if dry_run:
                count = await collection.count_documents({"tags": {"$not": {"$type": "array"}}})
                logger.info(f"[DRY RUN] Would normalize {count} tag fields")
            else:
                # Fix non-array tags
                async for doc in collection.find({"tags": {"$not": {"$type": "array"}}}):
                    await collection.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {"tags": []}}
                    )
                    cleanup_results['normalized_tags'] += 1
                
                # Fix non-string elements in tag arrays
                async for doc in collection.find({"tags": {"$type": "array"}}):
                    tags = doc.get('tags', [])
                    if tags and any(not isinstance(tag, str) for tag in tags):
                        clean_tags = [str(tag) for tag in tags if tag]
                        await collection.update_one(
                            {"_id": doc["_id"]},
                            {"$set": {"tags": clean_tags}}
                        )
                        cleanup_results['normalized_tags'] += 1
                
                logger.info(f"Normalized {cleanup_results['normalized_tags']} tag fields")
            
            # Remove duplicate products (keep the first one)
            pipeline = [
                {"$group": {"_id": "$name", "count": {"$sum": 1}, "docs": {"$push": "$$ROOT"}}},
                {"$match": {"count": {"$gt": 1}}}
            ]
            
            async for result in collection.aggregate(pipeline):
                docs = result['docs']
                # Keep the first document, remove the rest
                for doc in docs[1:]:
                    if dry_run:
                        logger.info(f"[DRY RUN] Would remove duplicate: {doc.get('name')} (ID: {doc['_id']})")
                    else:
                        await collection.delete_one({"_id": doc["_id"]})
                        cleanup_results['removed_duplicates'] += 1
                        logger.info(f"Removed duplicate product: {doc.get('name')} (ID: {doc['_id']})")
            
            logger.info(f"Data cleanup completed {'(dry run)' if dry_run else ''}")
            return cleanup_results
            
        except Exception as e:
            logger.error(f"Data cleanup failed: {e}")
            raise
    
    async def generate_validation_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive validation report.
        
        Returns:
            Dictionary with complete validation report
        """
        try:
            logger.info("Generating validation report...")
            
            # Run all validations
            schema_results = await self.validate_product_schema()
            integrity_results = await self.validate_data_integrity()
            
            # Get collection statistics
            collection = self.db.products
            total_count = await collection.count_documents({})
            active_count = await collection.count_documents({"active": True})
            featured_count = await collection.count_documents({"featured": True})
            
            report = {
                'timestamp': datetime.utcnow().isoformat(),
                'database': self.database_name,
                'collection_stats': {
                    'total_products': total_count,
                    'active_products': active_count,
                    'featured_products': featured_count
                },
                'schema_validation': schema_results,
                'integrity_validation': integrity_results,
                'recommendations': []
            }
            
            # Generate recommendations
            if schema_results['invalid_documents'] > 0:
                report['recommendations'].append(
                    f"Fix {schema_results['invalid_documents']} documents with schema violations"
                )
            
            if integrity_results['duplicate_names']:
                report['recommendations'].append(
                    f"Remove {len(integrity_results['duplicate_names'])} duplicate product names"
                )
            
            if integrity_results['invalid_prices']:
                report['recommendations'].append(
                    f"Fix {len(integrity_results['invalid_prices'])} products with invalid prices"
                )
            
            if integrity_results['missing_descriptions']:
                report['recommendations'].append(
                    f"Add descriptions to {len(integrity_results['missing_descriptions'])} products"
                )
            
            if not report['recommendations']:
                report['recommendations'].append("No issues found - data is clean!")
            
            logger.info("Validation report generated successfully")
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate validation report: {e}")
            raise


async def main():
    """Main validation function."""
    import os
    import json
    
    # Configuration
    mongodb_url = os.getenv('MONGODB_URL', 'mongodb://catalogue_user:catalogue_pass@localhost:27017/catalogue')
    database_name = os.getenv('MONGODB_DATABASE', 'catalogue')
    dry_run = os.getenv('DRY_RUN', 'true').lower() == 'true'
    cleanup = os.getenv('CLEANUP', 'false').lower() == 'true'
    
    logger.info("Starting MongoDB data validation...")
    logger.info(f"MongoDB URL: {mongodb_url}")
    logger.info(f"Database: {database_name}")
    logger.info(f"Dry run: {dry_run}")
    logger.info(f"Cleanup: {cleanup}")
    
    validator = DataValidator(mongodb_url, database_name)
    
    try:
        # Connect to database
        await validator.connect()
        
        # Generate validation report
        report = await validator.generate_validation_report()
        
        # Print report summary
        logger.info("=== VALIDATION REPORT ===")
        logger.info(f"Total products: {report['collection_stats']['total_products']}")
        logger.info(f"Valid documents: {report['schema_validation']['valid_documents']}")
        logger.info(f"Invalid documents: {report['schema_validation']['invalid_documents']}")
        
        if report['integrity_validation']['duplicate_names']:
            logger.warning(f"Duplicate names: {len(report['integrity_validation']['duplicate_names'])}")
        
        if report['integrity_validation']['invalid_prices']:
            logger.warning(f"Invalid prices: {len(report['integrity_validation']['invalid_prices'])}")
        
        logger.info("Recommendations:")
        for rec in report['recommendations']:
            logger.info(f"  - {rec}")
        
        # Perform cleanup if requested
        if cleanup:
            logger.info("Performing data cleanup...")
            cleanup_results = await validator.cleanup_invalid_data(dry_run=dry_run)
            logger.info("Cleanup results:")
            for key, value in cleanup_results.items():
                if value > 0:
                    logger.info(f"  {key}: {value}")
        
        # Save detailed report to file
        report_file = f"validation_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"Detailed report saved to: {report_file}")
        
        logger.info("Data validation completed successfully!")
        
    except Exception as e:
        logger.error(f"Data validation failed: {e}")
        raise
    finally:
        await validator.disconnect()


if __name__ == "__main__":
    asyncio.run(main())