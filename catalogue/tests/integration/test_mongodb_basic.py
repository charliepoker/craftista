"""
Basic MongoDB Integration Tests

This module provides basic integration tests for MongoDB operations
that can run without Docker containers using in-memory databases or mocks.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId

from models.product import Product, ProductCreate, ProductUpdate, ProductSearchFilters
from repository.mongodb_repository import MongoDBProductRepository


class TestMongoDBBasicIntegration:
    """Basic integration tests for MongoDB operations using mocks."""

    @pytest.fixture
    def mock_database(self):
        """Create a mock database for testing."""
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_db.products = mock_collection
        return mock_db

    @pytest.fixture
    def repository(self, mock_database):
        """Create repository instance with mock database."""
        repo = MongoDBProductRepository(mock_database)
        # Skip index creation for mock tests
        repo._indexes_created = True
        # Disable circuit breaker for tests
        repo.circuit_breaker = None
        return repo

    @pytest.fixture
    def sample_product_data(self):
        """Sample product data for testing."""
        return {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "name": "Test Product",
            "description": "Test description",
            "price": 19.99,
            "category": "test",
            "tags": ["test", "sample"],
            "active": True,
            "featured": False,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

    @pytest.mark.asyncio
    async def test_repository_initialization(self, mock_database):
        """Test repository initialization."""
        repo = MongoDBProductRepository(mock_database)
        assert repo.db == mock_database
        assert repo.collection == mock_database.products

    @pytest.mark.asyncio
    async def test_get_all_products_with_mock(self, repository, sample_product_data):
        """Test getting all products with mocked database."""
        # Setup mock response - need to use MagicMock for synchronous chaining
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[sample_product_data])
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.sort.return_value = mock_cursor
        
        repository.collection.find.return_value = mock_cursor
        
        # Execute test directly without circuit breaker
        products = await repository._get_all_products_internal()
        
        # Verify results
        assert len(products) == 1
        assert products[0].name == "Test Product"
        assert products[0].price == 19.99
        
        # Verify mock calls
        repository.collection.find.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_product_by_id_with_mock(self, repository, sample_product_data):
        """Test getting product by ID with mocked database."""
        # Setup mock response
        repository.collection.find_one.return_value = sample_product_data
        
        # Execute test
        product = await repository.get_product_by_id("507f1f77bcf86cd799439011")
        
        # Verify results
        assert product is not None
        assert product.name == "Test Product"
        assert str(product.id) == "507f1f77bcf86cd799439011"
        
        # Verify mock calls
        repository.collection.find_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_product_with_mock(self, repository):
        """Test creating product with mocked database."""
        # Setup mock response
        mock_result = MagicMock()
        mock_result.inserted_id = ObjectId("507f1f77bcf86cd799439011")
        repository.collection.insert_one.return_value = mock_result
        
        # Mock the get_product_by_id call that happens after creation
        created_product_data = {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "name": "New Product",
            "price": 25.00,
            "active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        repository.collection.find_one.return_value = created_product_data
        
        # Execute test
        product_data = ProductCreate(name="New Product", price=25.00)
        created_product = await repository.create_product(product_data)
        
        # Verify results
        assert created_product is not None
        assert created_product.name == "New Product"
        assert created_product.price == 25.00
        
        # Verify mock calls
        repository.collection.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_product_with_mock(self, repository, sample_product_data):
        """Test updating product with mocked database."""
        # Setup mock response for update
        mock_result = MagicMock()
        mock_result.matched_count = 1
        repository.collection.update_one.return_value = mock_result
        
        # Setup mock response for get_product_by_id
        updated_data = sample_product_data.copy()
        updated_data["name"] = "Updated Product"
        updated_data["updated_at"] = datetime.utcnow()
        repository.collection.find_one.return_value = updated_data
        
        # Execute test
        updates = ProductUpdate(name="Updated Product")
        updated_product = await repository.update_product("507f1f77bcf86cd799439011", updates)
        
        # Verify results
        assert updated_product is not None
        assert updated_product.name == "Updated Product"
        
        # Verify mock calls
        repository.collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_product_with_mock(self, repository):
        """Test deleting product with mocked database."""
        # Setup mock response
        mock_result = MagicMock()
        mock_result.deleted_count = 1
        repository.collection.delete_one.return_value = mock_result
        
        # Execute test
        success = await repository.delete_product("507f1f77bcf86cd799439011")
        
        # Verify results
        assert success is True
        
        # Verify mock calls
        repository.collection.delete_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_products_with_mock(self, repository, sample_product_data):
        """Test searching products with mocked database."""
        # Setup mock response
        mock_cursor = AsyncMock()
        search_result = sample_product_data.copy()
        search_result["score"] = 1.0  # Text search score
        mock_cursor.to_list.return_value = [search_result]
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        
        repository.collection.find.return_value = mock_cursor
        
        # Execute test
        products = await repository.search_products("test")
        
        # Verify results
        assert len(products) == 1
        assert products[0].name == "Test Product"
        
        # Verify mock calls
        repository.collection.find.assert_called_once()

    @pytest.mark.asyncio
    async def test_count_products_with_mock(self, repository):
        """Test counting products with mocked database."""
        # Setup mock response
        repository.collection.count_documents.return_value = 5
        
        # Execute test
        count = await repository.count_products()
        
        # Verify results
        assert count == 5
        
        # Verify mock calls
        repository.collection.count_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_featured_products_with_mock(self, repository, sample_product_data):
        """Test getting featured products with mocked database."""
        # Setup mock response
        mock_cursor = AsyncMock()
        featured_data = sample_product_data.copy()
        featured_data["featured"] = True
        mock_cursor.to_list.return_value = [featured_data]
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        
        repository.collection.find.return_value = mock_cursor
        
        # Execute test
        products = await repository.get_featured_products()
        
        # Verify results
        assert len(products) == 1
        assert products[0].featured is True
        
        # Verify mock calls
        repository.collection.find.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling_invalid_id(self, repository):
        """Test error handling for invalid ObjectId."""
        # Test with invalid ID format
        product = await repository.get_product_by_id("invalid_id")
        assert product is None
        
        # Test update with invalid ID
        updates = ProductUpdate(name="Updated")
        result = await repository.update_product("invalid_id", updates)
        assert result is None
        
        # Test delete with invalid ID
        success = await repository.delete_product("invalid_id")
        assert success is False

    @pytest.mark.asyncio
    async def test_data_sanitization(self, repository):
        """Test data sanitization in repository methods."""
        # Test with mock database
        mock_result = MagicMock()
        mock_result.inserted_id = ObjectId("507f1f77bcf86cd799439011")
        repository.collection.insert_one.return_value = mock_result
        
        # Mock the get_product_by_id response
        sanitized_data = {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "name": "Clean Product",  # Should be trimmed
            "tags": ["tag1", "tag2"],  # Should be cleaned
            "price": 19.99,
            "active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        repository.collection.find_one.return_value = sanitized_data
        
        # Test with data that needs sanitization
        product_data = ProductCreate(
            name="  Clean Product  ",  # Extra spaces
            tags=["TAG1", "tag1", "Tag2", ""],  # Mixed case and duplicates
            price=19.99
        )
        
        created_product = await repository.create_product(product_data)
        
        # Verify sanitization occurred in the call to insert_one
        call_args = repository.collection.insert_one.call_args[0][0]
        assert call_args["name"] == "Clean Product"  # Trimmed
        assert "tags" in call_args  # Tags should be processed

    @pytest.mark.asyncio
    async def test_concurrent_operations_simulation(self, repository):
        """Test simulation of concurrent operations."""
        # Setup mock responses for concurrent operations
        mock_results = []
        for i in range(5):
            mock_result = MagicMock()
            mock_result.inserted_id = ObjectId()
            mock_results.append(mock_result)
        
        repository.collection.insert_one.side_effect = mock_results
        
        # Mock get_product_by_id responses
        def mock_find_one(query):
            return {
                "_id": query["_id"],
                "name": f"Product {len(mock_results)}",
                "active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        
        repository.collection.find_one.side_effect = mock_find_one
        
        # Simulate concurrent operations
        async def create_product(index: int):
            product_data = ProductCreate(name=f"Product {index}")
            return await repository.create_product(product_data)
        
        tasks = [create_product(i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        # Verify all operations completed
        assert len(results) == 5
        assert all(product is not None for product in results)
        assert repository.collection.insert_one.call_count == 5