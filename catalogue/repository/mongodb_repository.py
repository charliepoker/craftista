"""
MongoDB implementation of the Product repository.

This module provides a concrete implementation of the ProductRepository interface
using MongoDB as the storage backend with Motor async driver.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo import IndexModel, TEXT, ASCENDING, DESCENDING
from pymongo.errors import PyMongoError, DuplicateKeyError, ConnectionFailure
from bson import ObjectId
from bson.errors import InvalidId

from models.product import Product, ProductCreate, ProductUpdate, ProductSearchFilters
from repository.base import ProductRepository, RepositoryError, ValidationError, ConnectionError
from database.circuit_breaker import get_circuit_breaker, get_fallback_handler, CircuitBreakerException

logger = logging.getLogger(__name__)


class MongoDBProductRepository(ProductRepository):
    """
    MongoDB implementation of the ProductRepository interface.
    
    This repository provides full CRUD operations, text search, and advanced
    querying capabilities using MongoDB as the storage backend.
    """

    def __init__(self, database: AsyncIOMotorDatabase):
        """
        Initialize the MongoDB repository.
        
        Args:
            database: AsyncIOMotorDatabase instance
        """
        self.db = database
        self.collection: AsyncIOMotorCollection = database.products if database else None
        self._indexes_created = False
        self.circuit_breaker = get_circuit_breaker("mongodb_repository")
        self.fallback_handler = get_fallback_handler()

    async def _ensure_indexes(self):
        """
        Ensure required indexes are created for optimal query performance.
        
        This method is called automatically on first use and creates indexes
        for text search, category filtering, and common query patterns.
        """
        if self._indexes_created:
            return

        try:
            indexes = [
                # Text search index for name and description
                IndexModel([("name", TEXT), ("description", TEXT)], name="text_search_idx"),
                
                # Category and active status for filtering
                IndexModel([("category", ASCENDING), ("active", ASCENDING)], name="category_active_idx"),
                
                # Tags for tag-based queries
                IndexModel([("tags", ASCENDING)], name="tags_idx"),
                
                # Featured and active for featured products
                IndexModel([("featured", ASCENDING), ("active", ASCENDING)], name="featured_active_idx"),
                
                # Created date for sorting recent products
                IndexModel([("created_at", DESCENDING)], name="created_at_idx"),
                
                # Price range queries
                IndexModel([("price", ASCENDING), ("active", ASCENDING)], name="price_active_idx"),
                
                # Inventory for stock filtering
                IndexModel([("inventory_count", ASCENDING), ("active", ASCENDING)], name="inventory_active_idx"),
            ]
            
            await self.collection.create_indexes(indexes)
            self._indexes_created = True
            logger.info("MongoDB indexes created successfully")
            
        except PyMongoError as e:
            logger.error(f"Failed to create indexes: {e}")
            raise RepositoryError(f"Failed to create database indexes: {e}", e)

    def _build_filter_query(self, filters: Optional[ProductSearchFilters]) -> Dict[str, Any]:
        """
        Build MongoDB query from search filters.
        
        Args:
            filters: Search filters to convert to MongoDB query
            
        Returns:
            MongoDB query dictionary
        """
        query = {}
        
        if not filters:
            return query

        # Active status filter
        if filters.active is not None:
            query["active"] = filters.active

        # Category filter
        if filters.category:
            query["category"] = {"$regex": f"^{filters.category}$", "$options": "i"}

        # Tags filter (match any of the provided tags)
        if filters.tags:
            query["tags"] = {"$in": [tag.lower() for tag in filters.tags]}

        # Featured filter
        if filters.featured is not None:
            query["featured"] = filters.featured

        # Price range filter
        price_conditions = []
        if filters.min_price is not None:
            price_conditions.append({"price": {"$gte": filters.min_price}})
        if filters.max_price is not None:
            price_conditions.append({"price": {"$lte": filters.max_price}})
        
        if price_conditions:
            if len(price_conditions) == 1:
                query.update(price_conditions[0])
            else:
                query["$and"] = price_conditions

        # In stock filter
        if filters.in_stock is not None:
            if filters.in_stock:
                query["inventory_count"] = {"$gt": 0}
            else:
                query["$or"] = [
                    {"inventory_count": {"$lte": 0}},
                    {"inventory_count": {"$exists": False}}
                ]

        return query

    def _sanitize_product_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize and validate product data before database operations.
        
        Args:
            data: Raw product data dictionary
            
        Returns:
            Sanitized product data dictionary
            
        Raises:
            ValidationError: If data validation fails
        """
        try:
            # Remove None values and empty strings
            sanitized = {k: v for k, v in data.items() if v is not None and v != ""}
            
            # Ensure tags are lowercase and unique
            if "tags" in sanitized and sanitized["tags"]:
                sanitized["tags"] = list(set(tag.lower().strip() for tag in sanitized["tags"] if tag.strip()))
            
            # Validate price is positive
            if "price" in sanitized and sanitized["price"] < 0:
                raise ValidationError("Price cannot be negative")
            
            # Validate inventory count is non-negative
            if "inventory_count" in sanitized and sanitized["inventory_count"] < 0:
                raise ValidationError("Inventory count cannot be negative")
            
            # Ensure name is not empty after stripping
            if "name" in sanitized:
                sanitized["name"] = sanitized["name"].strip()
                if not sanitized["name"]:
                    raise ValidationError("Product name cannot be empty")
            
            return sanitized
            
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Data validation failed: {e}", e)

    async def get_all_products(self, filters: Optional[ProductSearchFilters] = None, 
                              skip: int = 0, limit: int = 100) -> List[Product]:
        """Retrieve all products with optional filtering and pagination."""
        try:
            return await self.circuit_breaker.call(self._get_all_products_internal, filters, skip, limit)
        except CircuitBreakerException:
            logger.warning("Circuit breaker open, returning fallback products")
            return await self.fallback_handler.get_fallback_products()
        except Exception as e:
            logger.error(f"Failed to get products, returning fallback: {e}")
            return await self.fallback_handler.get_fallback_products()
    
    async def _get_all_products_internal(self, filters: Optional[ProductSearchFilters] = None, 
                                        skip: int = 0, limit: int = 100) -> List[Product]:
        """Internal method to retrieve all products."""
        if not self.collection:
            raise ConnectionError("Database connection not available")
            
        await self._ensure_indexes()
        
        query = self._build_filter_query(filters)
        
        cursor = self.collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
        documents = await cursor.to_list(length=limit)
        
        products = []
        for doc in documents:
            try:
                products.append(Product(**doc))
            except Exception as e:
                logger.warning(f"Failed to parse product document {doc.get('_id')}: {e}")
                continue
        
        # Cache successful response
        cache_key = f"products_{hash(str(filters))}_{skip}_{limit}"
        self.fallback_handler.cache_successful_response(cache_key, products)
        
        return products

    async def get_product_by_id(self, product_id: str) -> Optional[Product]:
        """Retrieve a single product by its ID."""
        try:
            await self._ensure_indexes()
            
            # Validate ObjectId format
            try:
                object_id = ObjectId(product_id)
            except InvalidId:
                return None
            
            document = await self.collection.find_one({"_id": object_id})
            
            if document:
                return Product(**document)
            return None
            
        except ConnectionFailure as e:
            raise ConnectionError(f"Database connection failed: {e}", e)
        except PyMongoError as e:
            raise RepositoryError(f"Failed to retrieve product {product_id}: {e}", e)

    async def create_product(self, product_data: ProductCreate) -> Product:
        """Create a new product."""
        try:
            await self._ensure_indexes()
            
            # Convert Pydantic model to dict and sanitize
            data = self._sanitize_product_data(product_data.dict(exclude_unset=True))
            
            # Add timestamps
            now = datetime.utcnow()
            data["created_at"] = now
            data["updated_at"] = now
            
            # Insert document
            result = await self.collection.insert_one(data)
            
            # Retrieve and return the created product
            created_product = await self.get_product_by_id(str(result.inserted_id))
            if not created_product:
                raise RepositoryError("Failed to retrieve created product")
            
            return created_product
            
        except ConnectionFailure as e:
            raise ConnectionError(f"Database connection failed: {e}", e)
        except DuplicateKeyError as e:
            raise ValidationError(f"Product with duplicate key already exists: {e}", e)
        except PyMongoError as e:
            raise RepositoryError(f"Failed to create product: {e}", e)

    async def update_product(self, product_id: str, updates: ProductUpdate) -> Optional[Product]:
        """Update an existing product."""
        try:
            await self._ensure_indexes()
            
            # Validate ObjectId format
            try:
                object_id = ObjectId(product_id)
            except InvalidId:
                return None
            
            # Convert Pydantic model to dict and sanitize
            update_data = self._sanitize_product_data(updates.dict(exclude_unset=True))
            
            if not update_data:
                # No updates provided, return current product
                return await self.get_product_by_id(product_id)
            
            # Add updated timestamp
            update_data["updated_at"] = datetime.utcnow()
            
            # Update document
            result = await self.collection.update_one(
                {"_id": object_id},
                {"$set": update_data}
            )
            
            if result.matched_count == 0:
                return None
            
            # Return updated product
            return await self.get_product_by_id(product_id)
            
        except ConnectionFailure as e:
            raise ConnectionError(f"Database connection failed: {e}", e)
        except PyMongoError as e:
            raise RepositoryError(f"Failed to update product {product_id}: {e}", e)

    async def delete_product(self, product_id: str) -> bool:
        """Delete a product by its ID."""
        try:
            await self._ensure_indexes()
            
            # Validate ObjectId format
            try:
                object_id = ObjectId(product_id)
            except InvalidId:
                return False
            
            result = await self.collection.delete_one({"_id": object_id})
            return result.deleted_count > 0
            
        except ConnectionFailure as e:
            raise ConnectionError(f"Database connection failed: {e}", e)
        except PyMongoError as e:
            raise RepositoryError(f"Failed to delete product {product_id}: {e}", e)

    async def search_products(self, query: str, filters: Optional[ProductSearchFilters] = None,
                             skip: int = 0, limit: int = 100) -> List[Product]:
        """Search products using text search with optional filters."""
        try:
            await self._ensure_indexes()
            
            # Build base filter query
            filter_query = self._build_filter_query(filters)
            
            # Add text search to the query
            search_query = {
                "$text": {"$search": query},
                **filter_query
            }
            
            # Execute search with text score sorting
            cursor = (self.collection
                     .find(search_query, {"score": {"$meta": "textScore"}})
                     .sort([("score", {"$meta": "textScore"}), ("created_at", -1)])
                     .skip(skip)
                     .limit(limit))
            
            documents = await cursor.to_list(length=limit)
            
            products = []
            for doc in documents:
                try:
                    # Remove the score field before creating Product object
                    doc.pop("score", None)
                    products.append(Product(**doc))
                except Exception as e:
                    logger.warning(f"Failed to parse product document {doc.get('_id')}: {e}")
                    continue
            
            return products
            
        except ConnectionFailure as e:
            raise ConnectionError(f"Database connection failed: {e}", e)
        except PyMongoError as e:
            raise RepositoryError(f"Failed to search products: {e}", e)

    async def get_featured_products(self, limit: int = 10) -> List[Product]:
        """Retrieve featured products."""
        try:
            await self._ensure_indexes()
            
            cursor = (self.collection
                     .find({"featured": True, "active": True})
                     .sort("created_at", -1)
                     .limit(limit))
            
            documents = await cursor.to_list(length=limit)
            
            products = []
            for doc in documents:
                try:
                    products.append(Product(**doc))
                except Exception as e:
                    logger.warning(f"Failed to parse product document {doc.get('_id')}: {e}")
                    continue
            
            return products
            
        except ConnectionFailure as e:
            raise ConnectionError(f"Database connection failed: {e}", e)
        except PyMongoError as e:
            raise RepositoryError(f"Failed to retrieve featured products: {e}", e)

    async def get_products_by_category(self, category: str, skip: int = 0, 
                                      limit: int = 100) -> List[Product]:
        """Retrieve products by category with pagination."""
        try:
            await self._ensure_indexes()
            
            query = {
                "category": {"$regex": f"^{category}$", "$options": "i"},
                "active": True
            }
            
            cursor = (self.collection
                     .find(query)
                     .sort("created_at", -1)
                     .skip(skip)
                     .limit(limit))
            
            documents = await cursor.to_list(length=limit)
            
            products = []
            for doc in documents:
                try:
                    products.append(Product(**doc))
                except Exception as e:
                    logger.warning(f"Failed to parse product document {doc.get('_id')}: {e}")
                    continue
            
            return products
            
        except ConnectionFailure as e:
            raise ConnectionError(f"Database connection failed: {e}", e)
        except PyMongoError as e:
            raise RepositoryError(f"Failed to retrieve products by category: {e}", e)

    async def count_products(self, filters: Optional[ProductSearchFilters] = None) -> int:
        """Count total number of products matching filters."""
        try:
            await self._ensure_indexes()
            
            query = self._build_filter_query(filters)
            count = await self.collection.count_documents(query)
            return count
            
        except ConnectionFailure as e:
            raise ConnectionError(f"Database connection failed: {e}", e)
        except PyMongoError as e:
            raise RepositoryError(f"Failed to count products: {e}", e)