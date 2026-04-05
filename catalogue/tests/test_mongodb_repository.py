"""
Unit tests for MongoDB Product Repository.

This module provides comprehensive unit tests for the MongoDBProductRepository
using mocked MongoDB operations to ensure fast, isolated testing.
Tests cover CRUD operations, search functionality, flexible query operations,
and error handling for connection failures and timeouts.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import PyMongoError, DuplicateKeyError, ConnectionFailure, ServerSelectionTimeoutError

from models.product import Product, ProductCreate, ProductUpdate, ProductSearchFilters
from repository.mongodb_repository import MongoDBProductRepository
from repository.base import RepositoryError, ValidationError, ConnectionError
from database.circuit_breaker import CircuitBreakerException


class TestMongoDBProductRepository:
    """Test suite for MongoDBProductRepository."""

    @pytest.fixture
    def mock_database(self):
        """Create a mock MongoDB database."""
        mock_db = AsyncMock()
        mock_collection = AsyncMock()
        mock_db.products = mock_collection
        return mock_db, mock_collection

    @pytest.fixture
    def repository(self, mock_database):
        """Create repository instance with mocked database."""
        mock_db, _ = mock_database
        repo = MongoDBProductRepository(mock_db)
        
        # Mock circuit breaker to avoid fallback behavior in tests
        repo.circuit_breaker = AsyncMock()
        repo.circuit_breaker.call = AsyncMock()
        repo.fallback_handler = AsyncMock()
        
        return repo

    @pytest.fixture
    def sample_product_data(self):
        """Sample product data for testing."""
        return {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "name": "Test Origami Crane",
            "description": "Beautiful test crane",
            "image_url": "/static/images/test.png",
            "price": 15.99,
            "category": "origami",
            "tags": ["paper", "craft"],
            "attributes": {"difficulty": "easy"},
            "active": True,
            "featured": False,
            "inventory_count": 10,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }

    @pytest.fixture
    def sample_product(self, sample_product_data):
        """Sample Product instance for testing."""
        return Product(**sample_product_data)

    @pytest.mark.asyncio
    async def test_get_all_products_success(self, repository, mock_database, sample_product_data):
        """Test successful retrieval of all products."""
        _, mock_collection = mock_database
        
        # Mock cursor behavior properly - use MagicMock for chaining
        mock_cursor = MagicMock()
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.to_list = AsyncMock(return_value=[sample_product_data])
        
        mock_collection.find = Mock(return_value=mock_cursor)
        mock_collection.create_indexes = AsyncMock()
        
        # Test the internal method directly to avoid circuit breaker complexity
        products = await repository._get_all_products_internal()
        
        # Assertions
        assert len(products) == 1
        assert products[0].name == "Test Origami Crane"
        assert products[0].price == 15.99
        mock_collection.find.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_products_with_filters(self, repository, mock_database, sample_product_data):
        """Test retrieval of products with filters."""
        _, mock_collection = mock_database
        
        # Mock cursor behavior
        mock_cursor = AsyncMock()
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.to_list.return_value = [sample_product_data]
        
        mock_collection.find.return_value = mock_cursor
        mock_collection.create_indexes = AsyncMock()
        
        # Create filters
        filters = ProductSearchFilters(
            category="origami",
            active=True,
            min_price=10.0,
            max_price=20.0
        )
        
        # Execute test
        products = await repository.get_all_products(filters=filters)
        
        # Assertions
        assert len(products) == 1
        # Verify filter query was built correctly
        call_args = mock_collection.find.call_args[0][0]
        assert "category" in call_args
        assert "active" in call_args
        assert call_args["active"] is True

    @pytest.mark.asyncio
    async def test_get_product_by_id_success(self, repository, mock_database, sample_product_data):
        """Test successful retrieval of product by ID."""
        _, mock_collection = mock_database
        
        mock_collection.find_one.return_value = sample_product_data
        mock_collection.create_indexes = AsyncMock()
        
        # Execute test
        product = await repository.get_product_by_id("507f1f77bcf86cd799439011")
        
        # Assertions
        assert product is not None
        assert product.name == "Test Origami Crane"
        mock_collection.find_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_product_by_id_invalid_id(self, repository, mock_database):
        """Test retrieval with invalid ObjectId."""
        _, mock_collection = mock_database
        mock_collection.create_indexes = AsyncMock()
        
        # Execute test with invalid ID
        product = await repository.get_product_by_id("invalid_id")
        
        # Assertions
        assert product is None
        mock_collection.find_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_product_by_id_not_found(self, repository, mock_database):
        """Test retrieval when product not found."""
        _, mock_collection = mock_database
        
        mock_collection.find_one.return_value = None
        mock_collection.create_indexes = AsyncMock()
        
        # Execute test
        product = await repository.get_product_by_id("507f1f77bcf86cd799439011")
        
        # Assertions
        assert product is None

    @pytest.mark.asyncio
    async def test_create_product_success(self, repository, mock_database, sample_product_data):
        """Test successful product creation."""
        _, mock_collection = mock_database
        
        # Mock insert result
        mock_result = MagicMock()
        mock_result.inserted_id = ObjectId("507f1f77bcf86cd799439011")
        mock_collection.insert_one.return_value = mock_result
        mock_collection.find_one.return_value = sample_product_data
        mock_collection.create_indexes = AsyncMock()
        
        # Create product data
        product_data = ProductCreate(
            name="Test Origami Crane",
            description="Beautiful test crane",
            price=15.99,
            category="origami"
        )
        
        # Execute test
        created_product = await repository.create_product(product_data)
        
        # Assertions
        assert created_product is not None
        assert created_product.name == "Test Origami Crane"
        mock_collection.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_product_validation_error(self, repository, mock_database):
        """Test product creation with validation error."""
        _, mock_collection = mock_database
        mock_collection.create_indexes = AsyncMock()
        
        # Pydantic validates before repository code runs
        with pytest.raises(Exception):  # Pydantic ValidationError
            ProductCreate(
                name="Test Product",
                price=-10.0  # Invalid negative price
            )
        
        assert "Price cannot be negative" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_product_duplicate_key_error(self, repository, mock_database):
        """Test product creation with duplicate key error."""
        _, mock_collection = mock_database
        
        mock_collection.insert_one.side_effect = DuplicateKeyError("Duplicate key")
        mock_collection.create_indexes = AsyncMock()
        
        product_data = ProductCreate(name="Test Product")
        
        # Execute test and expect ValidationError
        with pytest.raises(ValidationError):
            await repository.create_product(product_data)

    @pytest.mark.asyncio
    async def test_update_product_success(self, repository, mock_database, sample_product_data):
        """Test successful product update."""
        _, mock_collection = mock_database
        
        # Mock update result
        mock_result = MagicMock()
        mock_result.matched_count = 1
        mock_collection.update_one.return_value = mock_result
        mock_collection.find_one.return_value = sample_product_data
        mock_collection.create_indexes = AsyncMock()
        
        # Create update data
        update_data = ProductUpdate(name="Updated Product Name")
        
        # Execute test
        updated_product = await repository.update_product("507f1f77bcf86cd799439011", update_data)
        
        # Assertions
        assert updated_product is not None
        mock_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_product_not_found(self, repository, mock_database):
        """Test update when product not found."""
        _, mock_collection = mock_database
        
        # Mock update result with no matches
        mock_result = MagicMock()
        mock_result.matched_count = 0
        mock_collection.update_one.return_value = mock_result
        mock_collection.create_indexes = AsyncMock()
        
        update_data = ProductUpdate(name="Updated Name")
        
        # Execute test
        result = await repository.update_product("507f1f77bcf86cd799439011", update_data)
        
        # Assertions
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_product_success(self, repository, mock_database):
        """Test successful product deletion."""
        _, mock_collection = mock_database
        
        # Mock delete result
        mock_result = MagicMock()
        mock_result.deleted_count = 1
        mock_collection.delete_one.return_value = mock_result
        mock_collection.create_indexes = AsyncMock()
        
        # Execute test
        result = await repository.delete_product("507f1f77bcf86cd799439011")
        
        # Assertions
        assert result is True
        mock_collection.delete_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_product_not_found(self, repository, mock_database):
        """Test deletion when product not found."""
        _, mock_collection = mock_database
        
        # Mock delete result with no deletions
        mock_result = MagicMock()
        mock_result.deleted_count = 0
        mock_collection.delete_one.return_value = mock_result
        mock_collection.create_indexes = AsyncMock()
        
        # Execute test
        result = await repository.delete_product("507f1f77bcf86cd799439011")
        
        # Assertions
        assert result is False

    @pytest.mark.asyncio
    async def test_search_products_success(self, repository, mock_database, sample_product_data):
        """Test successful product search."""
        _, mock_collection = mock_database
        
        # Mock cursor behavior
        mock_cursor = AsyncMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.to_list.return_value = [sample_product_data]
        
        mock_collection.find.return_value = mock_cursor
        mock_collection.create_indexes = AsyncMock()
        
        # Execute test
        products = await repository.search_products("crane")
        
        # Assertions
        assert len(products) == 1
        assert products[0].name == "Test Origami Crane"
        
        # Verify text search query was used
        call_args = mock_collection.find.call_args[0][0]
        assert "$text" in call_args

    @pytest.mark.asyncio
    async def test_get_featured_products(self, repository, mock_database, sample_product_data):
        """Test retrieval of featured products."""
        _, mock_collection = mock_database
        
        # Modify sample data to be featured
        featured_data = sample_product_data.copy()
        featured_data["featured"] = True
        
        # Mock cursor behavior
        mock_cursor = AsyncMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.to_list.return_value = [featured_data]
        
        mock_collection.find.return_value = mock_cursor
        mock_collection.create_indexes = AsyncMock()
        
        # Execute test
        products = await repository.get_featured_products(limit=5)
        
        # Assertions
        assert len(products) == 1
        assert products[0].featured is True
        
        # Verify query filters for featured and active products
        call_args = mock_collection.find.call_args[0][0]
        assert call_args["featured"] is True
        assert call_args["active"] is True

    @pytest.mark.asyncio
    async def test_count_products(self, repository, mock_database):
        """Test product count functionality."""
        _, mock_collection = mock_database
        
        mock_collection.count_documents.return_value = 42
        mock_collection.create_indexes = AsyncMock()
        
        # Execute test
        count = await repository.count_products()
        
        # Assertions
        assert count == 42
        mock_collection.count_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_error_handling(self, repository, mock_database):
        """Test handling of connection errors."""
        _, mock_collection = mock_database
        
        mock_collection.find_one.side_effect = ConnectionFailure("Connection failed")
        mock_collection.create_indexes = AsyncMock()
        
        # Execute test and expect ConnectionError
        with pytest.raises(ConnectionError):
            await repository.get_product_by_id("507f1f77bcf86cd799439011")

    @pytest.mark.asyncio
    async def test_pymongo_error_handling(self, repository, mock_database):
        """Test handling of general PyMongo errors."""
        _, mock_collection = mock_database
        
        mock_collection.find_one.side_effect = PyMongoError("Database error")
        mock_collection.create_indexes = AsyncMock()
        
        # Execute test and expect RepositoryError
        with pytest.raises(RepositoryError):
            await repository.get_product_by_id("507f1f77bcf86cd799439011")

    @pytest.mark.asyncio
    async def test_data_sanitization(self, repository, mock_database):
        """Test data sanitization during product creation."""
        _, mock_collection = mock_database
        
        # Mock successful insert
        mock_result = MagicMock()
        mock_result.inserted_id = ObjectId("507f1f77bcf86cd799439011")
        mock_collection.insert_one.return_value = mock_result
        mock_collection.find_one.return_value = {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "name": "Test Product",
            "tags": ["tag1", "tag2"],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        mock_collection.create_indexes = AsyncMock()
        
        # Create product with mixed case tags
        product_data = ProductCreate(
            name="Test Product",
            tags=["Tag1", "TAG2", "  tag3  ", ""]  # Mixed case and empty tags
        )
        
        # Execute test
        await repository.create_product(product_data)
        
        # Verify sanitization was applied
        call_args = mock_collection.insert_one.call_args[0][0]
        assert "tags" in call_args
        # Tags should be lowercase and cleaned
        expected_tags = ["tag1", "tag2", "tag3"]
        assert call_args["tags"] == expected_tags

    @pytest.mark.asyncio
    async def test_build_filter_query(self, repository):
        """Test filter query building logic."""
        # Test with comprehensive filters
        filters = ProductSearchFilters(
            category="origami",
            tags=["paper", "craft"],
            active=True,
            featured=True,
            min_price=10.0,
            max_price=50.0,
            in_stock=True
        )
        
        query = repository._build_filter_query(filters)
        
        # Assertions
        assert query["active"] is True
        assert query["featured"] is True
        assert "category" in query
        assert "tags" in query
        assert query["tags"]["$in"] == ["paper", "craft"]
        assert "inventory_count" in query
        assert query["inventory_count"]["$gt"] == 0

    @pytest.mark.asyncio
    async def test_empty_database_connection(self):
        """Test repository behavior with no database connection."""
        repository = MongoDBProductRepository(None)
        
        # Execute test and expect ConnectionError
        with pytest.raises(ConnectionError):
            await repository.get_all_products()

    @pytest.mark.asyncio
    async def test_circuit_breaker_fallback(self, repository, mock_database):
        """Test circuit breaker fallback behavior."""
        _, mock_collection = mock_database
        
        # Mock circuit breaker to trigger fallback
        repository.circuit_breaker.call.side_effect = CircuitBreakerException("Circuit breaker open")
        repository.fallback_handler.get_fallback_products = AsyncMock(return_value=[])
        
        # Execute test
        products = await repository.get_all_products()
        
        # Assertions
        assert products == []
        repository.fallback_handler.get_fallback_products.assert_called_once()

    # Additional comprehensive tests for MongoDB operations

    @pytest.mark.asyncio
    async def test_search_products_with_complex_filters(self, repository, mock_database, sample_product_data):
        """Test search functionality with complex filters and text search."""
        _, mock_collection = mock_database
        
        # Create additional test data for search
        search_results = [
            sample_product_data,
            {
                "_id": ObjectId("507f1f77bcf86cd799439012"),
                "name": "Advanced Origami Dragon",
                "description": "Complex dragon design for experts",
                "price": 25.99,
                "category": "origami",
                "tags": ["paper", "advanced", "dragon"],
                "active": True,
                "featured": True,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
        ]
        
        # Mock cursor for search
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.to_list = AsyncMock(return_value=search_results)
        
        mock_collection.find = Mock(return_value=mock_cursor)
        mock_collection.create_indexes = AsyncMock()
        
        # Create complex search filters
        filters = ProductSearchFilters(
            category="origami",
            tags=["paper"],
            active=True,
            min_price=10.0,
            max_price=30.0,
            featured=None
        )
        
        # Execute search
        products = await repository.search_products("dragon", filters=filters)
        
        # Assertions
        assert len(products) == 2
        
        # Verify search query structure
        call_args = mock_collection.find.call_args[0][0]
        assert "$text" in call_args
        assert call_args["$text"]["$search"] == "dragon"
        assert "category" in call_args
        assert "tags" in call_args
        assert call_args["active"] is True

    @pytest.mark.asyncio
    async def test_flexible_query_operations_with_pagination(self, repository, mock_database):
        """Test flexible query operations with various filter combinations and pagination."""
        _, mock_collection = mock_database
        
        # Test data for pagination
        page1_data = [
            {
                "_id": ObjectId("507f1f77bcf86cd799439013"),
                "name": f"Product {i}",
                "category": "origami",
                "price": 10.0 + i,
                "active": True,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            for i in range(5)
        ]
        
        mock_cursor = MagicMock()
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.to_list = AsyncMock(return_value=page1_data)
        
        mock_collection.find = Mock(return_value=mock_cursor)
        mock_collection.create_indexes = AsyncMock()
        
        # Test with price range filter
        filters = ProductSearchFilters(
            min_price=10.0,
            max_price=15.0,
            in_stock=True
        )
        
        # Execute with pagination - use internal method to avoid circuit breaker
        products = await repository._get_all_products_internal(filters=filters, skip=10, limit=5)
        
        # Assertions
        assert len(products) == 5
        
        # Verify pagination parameters
        mock_cursor.skip.assert_called_with(10)
        mock_cursor.limit.assert_called_with(5)
        
        # Verify filter query
        call_args = mock_collection.find.call_args[0][0]
        assert "inventory_count" in call_args
        assert call_args["inventory_count"]["$gt"] == 0

    @pytest.mark.asyncio
    async def test_connection_timeout_error_handling(self, repository, mock_database):
        """Test handling of connection timeout errors."""
        _, mock_collection = mock_database
        
        # Mock timeout error
        mock_collection.find_one.side_effect = ServerSelectionTimeoutError("Connection timeout")
        mock_collection.create_indexes = AsyncMock()
        
        # Execute test and expect ConnectionError
        with pytest.raises(ConnectionError) as exc_info:
            await repository.get_product_by_id("507f1f77bcf86cd799439011")
        
        assert "Connection timeout" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_network_error_handling_with_retry_simulation(self, repository, mock_database):
        """Test handling of network errors and retry behavior simulation."""
        _, mock_collection = mock_database
        
        # Simulate network failure followed by success
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionFailure("Network error")
            return None
        
        mock_collection.find_one.side_effect = side_effect
        mock_collection.create_indexes = AsyncMock()
        
        # First call should raise ConnectionError
        with pytest.raises(ConnectionError):
            await repository.get_product_by_id("507f1f77bcf86cd799439011")
        
        # Second call should succeed (return None for not found)
        result = await repository.get_product_by_id("507f1f77bcf86cd799439011")
        assert result is None
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_search_with_text_scoring_and_sorting(self, repository, mock_database):
        """Test text search with scoring and proper sorting."""
        _, mock_collection = mock_database
        
        # Mock search results with text scores
        search_results = [
            {
                "_id": ObjectId("507f1f77bcf86cd799439014"),
                "name": "Origami Crane Tutorial",
                "description": "Learn to make beautiful cranes",
                "score": 1.5,  # Higher relevance score
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            },
            {
                "_id": ObjectId("507f1f77bcf86cd799439015"),
                "name": "Paper Crane Kit",
                "description": "Complete kit for crane making",
                "score": 1.2,  # Lower relevance score
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
        ]
        
        mock_cursor = AsyncMock()
        mock_cursor.sort = Mock(return_value=mock_cursor)
        mock_cursor.skip = Mock(return_value=mock_cursor)
        mock_cursor.limit = Mock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=search_results)
        
        mock_collection.find.return_value = mock_cursor
        mock_collection.create_indexes = AsyncMock()
        
        # Execute text search
        products = await repository.search_products("crane tutorial")
        
        # Assertions
        assert len(products) == 2
        
        # Verify text search query structure
        call_args = mock_collection.find.call_args
        query = call_args[0][0]
        projection = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get('projection', {})
        
        assert "$text" in query
        assert query["$text"]["$search"] == "crane tutorial"
        
        # Verify sorting by text score
        sort_calls = mock_cursor.sort.call_args_list
        assert len(sort_calls) > 0

    @pytest.mark.asyncio
    async def test_flexible_attribute_queries(self, repository, mock_database):
        """Test flexible queries on product attributes field."""
        _, mock_collection = mock_database
        
        # Test data with various attributes
        products_with_attributes = [
            {
                "_id": ObjectId("507f1f77bcf86cd799439016"),
                "name": "Beginner Origami Set",
                "attributes": {
                    "difficulty": "beginner",
                    "material": "paper",
                    "color": "multicolor",
                    "pieces": 50
                },
                "active": True,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            },
            {
                "_id": ObjectId("507f1f77bcf86cd799439017"),
                "name": "Expert Origami Collection",
                "attributes": {
                    "difficulty": "expert",
                    "material": "premium_paper",
                    "color": "gold",
                    "pieces": 25
                },
                "active": True,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
        ]
        
        mock_cursor = AsyncMock()
        mock_cursor.skip = Mock(return_value=mock_cursor)
        mock_cursor.limit = Mock(return_value=mock_cursor)
        mock_cursor.sort = Mock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=products_with_attributes)
        
        mock_collection.find.return_value = mock_cursor
        mock_collection.create_indexes = AsyncMock()
        
        # Execute query (simulating attribute-based filtering)
        products = await repository.get_all_products()
        
        # Assertions
        assert len(products) == 2
        assert products[0].attributes["difficulty"] == "beginner"
        assert products[1].attributes["difficulty"] == "expert"
        
        # Verify both products have flexible attributes
        for product in products:
            assert "difficulty" in product.attributes
            assert "material" in product.attributes
            assert isinstance(product.attributes["pieces"], int)

    @pytest.mark.asyncio
    async def test_concurrent_operations_simulation(self, repository, mock_database):
        """Test repository behavior under concurrent operations."""
        _, mock_collection = mock_database
        
        # Mock successful operations
        mock_collection.find_one.return_value = {
            "_id": ObjectId("507f1f77bcf86cd799439018"),
            "name": "Concurrent Test Product",
            "active": True,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        mock_collection.create_indexes = AsyncMock()
        
        # Simulate concurrent read operations
        async def concurrent_read():
            return await repository.get_product_by_id("507f1f77bcf86cd799439018")
        
        # Execute multiple concurrent operations
        tasks = [concurrent_read() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        # Assertions
        assert len(results) == 10
        assert all(result is not None for result in results)
        assert all(result.name == "Concurrent Test Product" for result in results)
        
        # Verify all operations called the database
        assert mock_collection.find_one.call_count == 10

    @pytest.mark.asyncio
    async def test_database_unavailable_error_handling(self, repository):
        """Test handling when database connection is completely unavailable."""
        # Create repository with no database connection
        repo_no_db = MongoDBProductRepository(None)
        
        # Execute test and expect ConnectionError
        with pytest.raises(ConnectionError) as exc_info:
            await repo_no_db.get_all_products()
        
        assert "Database connection not available" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_malformed_document_handling(self, repository, mock_database):
        """Test handling of malformed documents in database responses."""
        _, mock_collection = mock_database
        
        # Mock response with malformed documents
        malformed_docs = [
            {
                "_id": ObjectId("507f1f77bcf86cd799439019"),
                "name": "Valid Product",
                "active": True,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            },
            {
                "_id": ObjectId("507f1f77bcf86cd79943901a"),
                "name": None,  # Invalid: name cannot be None
                "active": "invalid_boolean",  # Invalid: should be boolean
                "created_at": "invalid_date"  # Invalid: should be datetime
            },
            {
                "_id": ObjectId("507f1f77bcf86cd79943901b"),
                "name": "Another Valid Product",
                "active": True,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
        ]
        
        mock_cursor = AsyncMock()
        mock_cursor.skip = Mock(return_value=mock_cursor)
        mock_cursor.limit = Mock(return_value=mock_cursor)
        mock_cursor.sort = Mock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=malformed_docs)
        
        mock_collection.find.return_value = mock_cursor
        mock_collection.create_indexes = AsyncMock()
        
        # Mock circuit breaker
        repository.circuit_breaker.call.side_effect = lambda func, *args, **kwargs: func(*args, **kwargs)
        
        # Execute test
        products = await repository.get_all_products()
        
        # Assertions - should only return valid products, skip malformed ones
        assert len(products) == 2
        assert products[0].name == "Valid Product"
        assert products[1].name == "Another Valid Product"

    @pytest.mark.asyncio
    async def test_index_creation_failure_handling(self, repository, mock_database):
        """Test handling of index creation failures."""
        _, mock_collection = mock_database
        
        # Mock index creation failure
        mock_collection.create_indexes.side_effect = PyMongoError("Index creation failed")
        
        # Execute test and expect RepositoryError
        with pytest.raises(RepositoryError) as exc_info:
            await repository.get_all_products()
        
        assert "Failed to create database indexes" in str(exc_info.value)

    def test_sanitize_product_data_validation_errors(self, repository):
        """Test data sanitization validation errors."""
        # Test negative price
        with pytest.raises(ValidationError) as exc_info:
            repository._sanitize_product_data({"price": -10.0})
        assert "Price cannot be negative" in str(exc_info.value)
        
        # Test negative inventory
        with pytest.raises(ValidationError) as exc_info:
            repository._sanitize_product_data({"inventory_count": -5})
        assert "Inventory count cannot be negative" in str(exc_info.value)
        
        # Test empty name
        with pytest.raises(ValidationError) as exc_info:
            repository._sanitize_product_data({"name": "   "})
        assert "Product name cannot be empty" in str(exc_info.value)

    def test_sanitize_product_data_success(self, repository):
        """Test successful data sanitization."""
        input_data = {
            "name": "  Test Product  ",
            "tags": ["Tag1", "TAG2", "  tag3  ", "", "tag1"],  # Duplicates and mixed case
            "price": 15.99,
            "inventory_count": 10,
            "description": None,
            "empty_field": ""
        }
        
        result = repository._sanitize_product_data(input_data)
        
        # Assertions
        assert result["name"] == "Test Product"  # Trimmed
        assert result["tags"] == ["tag1", "tag2", "tag3"]  # Lowercase, unique, cleaned
        assert result["price"] == 15.99
        assert result["inventory_count"] == 10
        assert "description" not in result  # None values removed
        assert "empty_field" not in result  # Empty strings removed


if __name__ == "__main__":
    pytest.main([__file__])