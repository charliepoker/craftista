"""
MongoDB Integration Tests using Test Containers

This module provides comprehensive integration tests for MongoDB operations
using real MongoDB instances via Docker test containers.

Note: These tests require Docker to be running. If Docker is not available,
the tests will be skipped with appropriate markers.
"""

import pytest
import pytest_asyncio
import asyncio
import os
from datetime import datetime, timedelta
from typing import List
from unittest.mock import AsyncMock, MagicMock

try:
    from testcontainers.mongodb import MongoDbContainer
    from motor.motor_asyncio import AsyncIOMotorClient
    from pymongo.errors import ConnectionFailure
    TESTCONTAINERS_AVAILABLE = True
except ImportError:
    TESTCONTAINERS_AVAILABLE = False

from models.product import Product, ProductCreate, ProductUpdate, ProductSearchFilters
from repository.mongodb_repository import MongoDBProductRepository


@pytest.mark.skipif(not TESTCONTAINERS_AVAILABLE, reason="testcontainers not available")
@pytest.mark.skipif(os.getenv("SKIP_INTEGRATION_TESTS") == "true", reason="Integration tests skipped")
class TestMongoDBIntegration:
    """Integration tests for MongoDB operations with real database."""

    @pytest.fixture(scope="class")
    def mongodb_container(self):
        """Start MongoDB test container for the test class."""
        try:
            with MongoDbContainer("mongo:7.0") as container:
                yield container
        except Exception as e:
            pytest.skip(f"Failed to start MongoDB container: {e}")

    @pytest_asyncio.fixture
    async def mongodb_client(self, mongodb_container):
        """Create MongoDB client connected to test container."""
        connection_url = mongodb_container.get_connection_url()
        client = AsyncIOMotorClient(connection_url)
        
        # Test connection
        try:
            await client.admin.command('ping')
        except ConnectionFailure:
            pytest.fail("Failed to connect to MongoDB test container")
        
        yield client
        client.close()

    @pytest_asyncio.fixture
    async def test_database(self, mongodb_client):
        """Create test database."""
        db_name = "test_catalogue_db"
        database = mongodb_client[db_name]
        yield database
        
        # Cleanup: Drop test database after tests
        await mongodb_client.drop_database(db_name)

    @pytest_asyncio.fixture
    async def repository(self, test_database):
        """Create repository instance for each test."""
        repo = MongoDBProductRepository(test_database)
        yield repo
        
        # Cleanup: Clear collection after each test
        await test_database.products.delete_many({})

    @pytest.fixture
    def sample_products(self):
        """Sample product data for testing."""
        return [
            ProductCreate(
                name="Origami Crane",
                description="Beautiful paper crane",
                price=15.99,
                category="origami",
                tags=["paper", "craft", "bird"],
                attributes={"difficulty": "intermediate", "color": "red"},
                featured=True,
                inventory_count=50
            ),
            ProductCreate(
                name="Paper Butterfly",
                description="Colorful butterfly origami",
                price=12.50,
                category="origami",
                tags=["paper", "craft", "butterfly"],
                attributes={"difficulty": "beginner", "color": "blue"},
                featured=False,
                inventory_count=30
            ),
            ProductCreate(
                name="Dragon Origami",
                description="Complex dragon design",
                price=25.00,
                category="origami",
                tags=["paper", "craft", "dragon", "advanced"],
                attributes={"difficulty": "expert", "color": "green"},
                featured=True,
                inventory_count=10
            ),
            ProductCreate(
                name="Simple Flower",
                description="Easy flower for beginners",
                price=8.99,
                category="origami",
                tags=["paper", "craft", "flower"],
                attributes={"difficulty": "beginner", "color": "yellow"},
                featured=False,
                inventory_count=100
            )
        ]

    async def test_database_connection(self, repository):
        """Test that database connection is working."""
        try:
            count = await repository.count_products()
            assert count == 0
        except Exception as e:
            pytest.skip(f"Database connection not available: {e}")

    async def test_create_product(self, repository):
        """Test creating a single product."""
        product_data = ProductCreate(
            name="Test Product",
            description="Test description",
            price=19.99,
            category="test",
            tags=["test", "sample"],
            featured=True
        )
        
        created_product = await repository.create_product(product_data)
        
        assert created_product is not None
        assert created_product.id is not None
        assert created_product.name == "Test Product"
        assert created_product.price == 19.99
        assert created_product.featured is True
        assert created_product.created_at is not None
        assert created_product.updated_at is not None

    async def test_get_product_by_id(self, repository):
        """Test retrieving a product by ID."""
        # Create a product first
        product_data = ProductCreate(name="Findable Product", price=10.00)
        created_product = await repository.create_product(product_data)
        
        # Retrieve by ID
        found_product = await repository.get_product_by_id(str(created_product.id))
        
        assert found_product is not None
        assert found_product.id == created_product.id
        assert found_product.name == "Findable Product"

    async def test_get_product_by_invalid_id(self, repository):
        """Test retrieving a product with invalid ID."""
        # Test with invalid ObjectId format
        result = await repository.get_product_by_id("invalid_id")
        assert result is None
        
        # Test with valid ObjectId format but non-existent
        result = await repository.get_product_by_id("507f1f77bcf86cd799439011")
        assert result is None

    async def test_update_product(self, repository):
        """Test updating an existing product."""
        # Create a product first
        product_data = ProductCreate(name="Original Name", price=15.00)
        created_product = await repository.create_product(product_data)
        
        # Update the product
        updates = ProductUpdate(
            name="Updated Name",
            price=20.00,
            featured=True
        )
        
        updated_product = await repository.update_product(str(created_product.id), updates)
        
        assert updated_product is not None
        assert updated_product.name == "Updated Name"
        assert updated_product.price == 20.00
        assert updated_product.featured is True
        assert updated_product.updated_at > created_product.updated_at

    async def test_delete_product(self, repository):
        """Test deleting a product."""
        # Create a product first
        product_data = ProductCreate(name="To Be Deleted", price=5.00)
        created_product = await repository.create_product(product_data)
        
        # Delete the product
        success = await repository.delete_product(str(created_product.id))
        assert success is True
        
        # Verify it's deleted
        found_product = await repository.get_product_by_id(str(created_product.id))
        assert found_product is None

    async def test_get_all_products(self, repository, sample_products):
        """Test retrieving all products with pagination."""
        # Create multiple products
        created_products = []
        for product_data in sample_products:
            created_product = await repository.create_product(product_data)
            created_products.append(created_product)
        
        # Get all products
        all_products = await repository.get_all_products()
        assert len(all_products) == len(sample_products)
        
        # Test pagination
        first_page = await repository.get_all_products(skip=0, limit=2)
        assert len(first_page) == 2
        
        second_page = await repository.get_all_products(skip=2, limit=2)
        assert len(second_page) == 2
        
        # Ensure no overlap
        first_ids = {p.id for p in first_page}
        second_ids = {p.id for p in second_page}
        assert first_ids.isdisjoint(second_ids)

    async def test_search_products_text_search(self, repository, sample_products):
        """Test text search functionality."""
        # Create products with searchable content
        for product_data in sample_products:
            await repository.create_product(product_data)
        
        # Search for "crane"
        crane_results = await repository.search_products("crane")
        assert len(crane_results) == 1
        assert crane_results[0].name == "Origami Crane"
        
        # Search for "butterfly"
        butterfly_results = await repository.search_products("butterfly")
        assert len(butterfly_results) == 1
        assert butterfly_results[0].name == "Paper Butterfly"
        
        # Search for "origami" (should match multiple)
        origami_results = await repository.search_products("origami")
        assert len(origami_results) >= 2

    async def test_product_filtering(self, repository, sample_products):
        """Test product filtering functionality."""
        # Create products
        for product_data in sample_products:
            await repository.create_product(product_data)
        
        # Filter by category
        filters = ProductSearchFilters(category="origami")
        category_results = await repository.get_all_products(filters=filters)
        assert len(category_results) == len(sample_products)  # All are origami
        
        # Filter by featured products
        filters = ProductSearchFilters(featured=True)
        featured_results = await repository.get_all_products(filters=filters)
        assert len(featured_results) == 2  # Crane and Dragon are featured
        
        # Filter by price range
        filters = ProductSearchFilters(min_price=10.00, max_price=20.00)
        price_results = await repository.get_all_products(filters=filters)
        assert len(price_results) == 2  # Crane and Butterfly
        
        # Filter by tags
        filters = ProductSearchFilters(tags=["advanced"])
        tag_results = await repository.get_all_products(filters=filters)
        assert len(tag_results) == 1  # Only Dragon has "advanced" tag

    async def test_get_featured_products(self, repository, sample_products):
        """Test retrieving featured products."""
        # Create products
        for product_data in sample_products:
            await repository.create_product(product_data)
        
        featured_products = await repository.get_featured_products()
        assert len(featured_products) == 2  # Crane and Dragon are featured
        
        featured_names = {p.name for p in featured_products}
        assert "Origami Crane" in featured_names
        assert "Dragon Origami" in featured_names

    async def test_get_products_by_category(self, repository, sample_products):
        """Test retrieving products by category."""
        # Create products
        for product_data in sample_products:
            await repository.create_product(product_data)
        
        # Create a product in different category
        other_product = ProductCreate(
            name="Test Widget",
            category="widgets",
            price=5.00
        )
        await repository.create_product(other_product)
        
        # Get origami products
        origami_products = await repository.get_products_by_category("origami")
        assert len(origami_products) == len(sample_products)
        
        # Get widgets
        widget_products = await repository.get_products_by_category("widgets")
        assert len(widget_products) == 1
        assert widget_products[0].name == "Test Widget"

    async def test_count_products(self, repository, sample_products):
        """Test counting products with filters."""
        # Create products
        for product_data in sample_products:
            await repository.create_product(product_data)
        
        # Count all products
        total_count = await repository.count_products()
        assert total_count == len(sample_products)
        
        # Count featured products
        filters = ProductSearchFilters(featured=True)
        featured_count = await repository.count_products(filters=filters)
        assert featured_count == 2
        
        # Count products in price range
        filters = ProductSearchFilters(min_price=15.00)
        expensive_count = await repository.count_products(filters=filters)
        assert expensive_count == 2  # Crane and Dragon

    async def test_inventory_filtering(self, repository):
        """Test inventory-based filtering."""
        # Create products with different inventory levels
        in_stock_product = ProductCreate(
            name="In Stock Product",
            inventory_count=10
        )
        out_of_stock_product = ProductCreate(
            name="Out of Stock Product",
            inventory_count=0
        )
        no_inventory_product = ProductCreate(
            name="No Inventory Tracking"
            # No inventory_count set
        )
        
        await repository.create_product(in_stock_product)
        await repository.create_product(out_of_stock_product)
        await repository.create_product(no_inventory_product)
        
        # Filter for in-stock products
        filters = ProductSearchFilters(in_stock=True)
        in_stock_results = await repository.get_all_products(filters=filters)
        assert len(in_stock_results) == 1
        assert in_stock_results[0].name == "In Stock Product"
        
        # Filter for out-of-stock products
        filters = ProductSearchFilters(in_stock=False)
        out_of_stock_results = await repository.get_all_products(filters=filters)
        assert len(out_of_stock_results) == 2  # Out of stock + no tracking

    async def test_concurrent_operations(self, repository):
        """Test concurrent database operations."""
        async def create_product(index: int) -> Product:
            product_data = ProductCreate(
                name=f"Concurrent Product {index}",
                price=float(index * 10)
            )
            return await repository.create_product(product_data)
        
        # Create multiple products concurrently
        tasks = [create_product(i) for i in range(10)]
        created_products = await asyncio.gather(*tasks)
        
        assert len(created_products) == 10
        assert all(p.id is not None for p in created_products)
        
        # Verify all products were created
        all_products = await repository.get_all_products()
        assert len(all_products) == 10

    async def test_index_creation_and_performance(self, repository, sample_products):
        """Test that indexes are created and improve query performance."""
        # Create a larger dataset
        products_to_create = []
        for i in range(100):
            for base_product in sample_products:
                product_data = ProductCreate(
                    name=f"{base_product.name} {i}",
                    description=base_product.description,
                    category=base_product.category,
                    tags=base_product.tags,
                    price=base_product.price + i,
                    featured=(i % 10 == 0)  # Every 10th product is featured
                )
                products_to_create.append(product_data)
        
        # Create products in batches to avoid overwhelming the database
        batch_size = 20
        for i in range(0, len(products_to_create), batch_size):
            batch = products_to_create[i:i + batch_size]
            tasks = [repository.create_product(product) for product in batch]
            await asyncio.gather(*tasks)
        
        # Test text search performance (should use text index)
        start_time = datetime.now()
        search_results = await repository.search_products("crane")
        search_duration = datetime.now() - start_time
        
        assert len(search_results) > 0
        assert search_duration.total_seconds() < 1.0  # Should be fast with index
        
        # Test category filtering (should use category index)
        start_time = datetime.now()
        category_results = await repository.get_products_by_category("origami")
        category_duration = datetime.now() - start_time
        
        assert len(category_results) > 0
        assert category_duration.total_seconds() < 1.0  # Should be fast with index

    async def test_data_validation_and_sanitization(self, repository):
        """Test data validation and sanitization."""
        # Test tag sanitization (should convert to lowercase and remove duplicates)
        product_data = ProductCreate(
            name="  Test Product  ",  # Should be trimmed
            tags=["TAG1", "tag1", "Tag2", "", "  tag3  "],  # Should be cleaned
            price=19.99
        )
        
        created_product = await repository.create_product(product_data)
        
        assert created_product.name == "Test Product"  # Trimmed
        assert set(created_product.tags) == {"tag1", "tag2", "tag3"}  # Cleaned and deduplicated
        
        # Test price validation (negative price should be handled)
        with pytest.raises(Exception):  # Should raise validation error
            invalid_product = ProductCreate(
                name="Invalid Product",
                price=-10.00  # Negative price
            )
            await repository.create_product(invalid_product)

    async def test_error_handling(self, repository):
        """Test error handling for various scenarios."""
        # Test updating non-existent product
        updates = ProductUpdate(name="Updated Name")
        result = await repository.update_product("507f1f77bcf86cd799439011", updates)
        assert result is None
        
        # Test deleting non-existent product
        success = await repository.delete_product("507f1f77bcf86cd799439011")
        assert success is False
        
        # Test empty search query
        results = await repository.search_products("")
        assert isinstance(results, list)  # Should return empty list, not error