"""
Unit tests for MockProductRepository.

This module tests the mock repository implementation to ensure it behaves
correctly and can be used reliably in other tests.
"""

import pytest
from datetime import datetime
from models.product import Product, ProductCreate, ProductUpdate, ProductSearchFilters
from tests.mocks.mock_product_repository import MockProductRepository
from repository.base import RepositoryError, ValidationError


class TestMockProductRepository:
    """Test suite for MockProductRepository."""

    @pytest.fixture
    def repository(self):
        """Create a fresh mock repository for each test."""
        return MockProductRepository()

    @pytest.fixture
    def sample_products(self, repository):
        """Create sample products for testing."""
        products = [
            Product(
                id="1",
                name="Origami Crane",
                description="Beautiful paper crane",
                price=15.99,
                category="origami",
                tags=["paper", "bird", "easy"],
                active=True,
                featured=True,
                inventory_count=10,
                created_at=datetime(2024, 1, 1, 12, 0, 0),
                updated_at=datetime(2024, 1, 1, 12, 0, 0)
            ),
            Product(
                id="2",
                name="Origami Butterfly",
                description="Colorful butterfly design",
                price=12.50,
                category="origami",
                tags=["paper", "insect", "medium"],
                active=True,
                featured=False,
                inventory_count=5,
                created_at=datetime(2024, 1, 2, 12, 0, 0),
                updated_at=datetime(2024, 1, 2, 12, 0, 0)
            ),
            Product(
                id="3",
                name="Paper Flower",
                description="Delicate paper flower",
                price=8.75,
                category="paper-craft",
                tags=["paper", "flower", "easy"],
                active=False,  # Inactive product
                featured=False,
                inventory_count=0,
                created_at=datetime(2024, 1, 3, 12, 0, 0),
                updated_at=datetime(2024, 1, 3, 12, 0, 0)
            )
        ]
        
        for product in products:
            repository.add_test_product(product)
        
        return products

    @pytest.mark.asyncio
    async def test_get_all_products_no_filters(self, repository, sample_products):
        """Test retrieving all products without filters."""
        products = await repository.get_all_products()
        
        # Should return all products (including inactive ones)
        assert len(products) == 3
        
        # Should be sorted by created_at descending (newest first)
        assert products[0].name == "Paper Flower"  # Created on Jan 3
        assert products[1].name == "Origami Butterfly"  # Created on Jan 2
        assert products[2].name == "Origami Crane"  # Created on Jan 1

    @pytest.mark.asyncio
    async def test_get_all_products_with_active_filter(self, repository, sample_products):
        """Test retrieving products with active filter."""
        filters = ProductSearchFilters(active=True)
        products = await repository.get_all_products(filters=filters)
        
        # Should return only active products
        assert len(products) == 2
        assert all(product.active for product in products)

    @pytest.mark.asyncio
    async def test_get_all_products_with_category_filter(self, repository, sample_products):
        """Test retrieving products with category filter."""
        filters = ProductSearchFilters(category="origami")
        products = await repository.get_all_products(filters=filters)
        
        # Should return only origami products
        assert len(products) == 2
        assert all(product.category == "origami" for product in products)

    @pytest.mark.asyncio
    async def test_get_all_products_with_price_range_filter(self, repository, sample_products):
        """Test retrieving products with price range filter."""
        filters = ProductSearchFilters(min_price=10.0, max_price=20.0)
        products = await repository.get_all_products(filters=filters)
        
        # Should return products within price range
        assert len(products) == 2
        for product in products:
            assert 10.0 <= product.price <= 20.0

    @pytest.mark.asyncio
    async def test_get_all_products_with_tags_filter(self, repository, sample_products):
        """Test retrieving products with tags filter."""
        filters = ProductSearchFilters(tags=["bird"])
        products = await repository.get_all_products(filters=filters)
        
        # Should return products with "bird" tag
        assert len(products) == 1
        assert products[0].name == "Origami Crane"

    @pytest.mark.asyncio
    async def test_get_all_products_with_pagination(self, repository, sample_products):
        """Test pagination functionality."""
        # Get first page
        page1 = await repository.get_all_products(skip=0, limit=2)
        assert len(page1) == 2
        
        # Get second page
        page2 = await repository.get_all_products(skip=2, limit=2)
        assert len(page2) == 1
        
        # Ensure no overlap
        page1_ids = {p.id for p in page1}
        page2_ids = {p.id for p in page2}
        assert page1_ids.isdisjoint(page2_ids)

    @pytest.mark.asyncio
    async def test_get_product_by_id_success(self, repository, sample_products):
        """Test successful product retrieval by ID."""
        product = await repository.get_product_by_id("1")
        
        assert product is not None
        assert product.name == "Origami Crane"
        assert product.id == "1"

    @pytest.mark.asyncio
    async def test_get_product_by_id_not_found(self, repository, sample_products):
        """Test product retrieval with non-existent ID."""
        product = await repository.get_product_by_id("999")
        assert product is None

    @pytest.mark.asyncio
    async def test_create_product_success(self, repository):
        """Test successful product creation."""
        product_data = ProductCreate(
            name="New Origami Dragon",
            description="Complex dragon design",
            price=25.99,
            category="origami",
            tags=["paper", "dragon", "hard"],
            active=True,
            featured=True,
            inventory_count=3
        )
        
        created_product = await repository.create_product(product_data)
        
        assert created_product is not None
        assert created_product.name == "New Origami Dragon"
        assert created_product.price == 25.99
        assert created_product.id is not None
        assert created_product.created_at is not None
        assert created_product.updated_at is not None

    @pytest.mark.asyncio
    async def test_create_product_validation_errors(self, repository):
        """Test product creation validation errors."""
        # Test negative price
        with pytest.raises(ValidationError) as exc_info:
            await repository.create_product(ProductCreate(name="Test", price=-10.0))
        assert "Price cannot be negative" in str(exc_info.value)
        
        # Test negative inventory
        with pytest.raises(ValidationError) as exc_info:
            await repository.create_product(ProductCreate(name="Test", inventory_count=-5))
        assert "Inventory count cannot be negative" in str(exc_info.value)
        
        # Test empty name
        with pytest.raises(ValidationError) as exc_info:
            await repository.create_product(ProductCreate(name="   "))
        assert "Product name cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_product_tag_cleaning(self, repository):
        """Test that tags are properly cleaned during creation."""
        product_data = ProductCreate(
            name="Test Product",
            tags=["Tag1", "TAG2", "  tag3  ", "", "tag1"]  # Mixed case, spaces, empty, duplicate
        )
        
        created_product = await repository.create_product(product_data)
        
        # Tags should be lowercase, trimmed, and deduplicated
        expected_tags = ["tag1", "tag2", "tag3"]
        assert set(created_product.tags) == set(expected_tags)

    @pytest.mark.asyncio
    async def test_update_product_success(self, repository, sample_products):
        """Test successful product update."""
        updates = ProductUpdate(
            name="Updated Crane Name",
            price=18.99,
            featured=False
        )
        
        updated_product = await repository.update_product("1", updates)
        
        assert updated_product is not None
        assert updated_product.name == "Updated Crane Name"
        assert updated_product.price == 18.99
        assert updated_product.featured is False
        assert updated_product.updated_at > updated_product.created_at

    @pytest.mark.asyncio
    async def test_update_product_not_found(self, repository, sample_products):
        """Test updating non-existent product."""
        updates = ProductUpdate(name="New Name")
        result = await repository.update_product("999", updates)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_product_validation_errors(self, repository, sample_products):
        """Test product update validation errors."""
        # Test negative price
        with pytest.raises(ValidationError):
            await repository.update_product("1", ProductUpdate(price=-10.0))
        
        # Test empty name
        with pytest.raises(ValidationError):
            await repository.update_product("1", ProductUpdate(name="   "))

    @pytest.mark.asyncio
    async def test_delete_product_success(self, repository, sample_products):
        """Test successful product deletion."""
        result = await repository.delete_product("1")
        assert result is True
        
        # Verify product is deleted
        product = await repository.get_product_by_id("1")
        assert product is None

    @pytest.mark.asyncio
    async def test_delete_product_not_found(self, repository, sample_products):
        """Test deleting non-existent product."""
        result = await repository.delete_product("999")
        assert result is False

    @pytest.mark.asyncio
    async def test_search_products_by_name(self, repository, sample_products):
        """Test product search by name."""
        products = await repository.search_products("crane")
        
        assert len(products) == 1
        assert products[0].name == "Origami Crane"

    @pytest.mark.asyncio
    async def test_search_products_by_description(self, repository, sample_products):
        """Test product search by description."""
        products = await repository.search_products("colorful")
        
        assert len(products) == 1
        assert products[0].name == "Origami Butterfly"

    @pytest.mark.asyncio
    async def test_search_products_by_tags(self, repository, sample_products):
        """Test product search by tags."""
        products = await repository.search_products("insect")
        
        assert len(products) == 1
        assert products[0].name == "Origami Butterfly"

    @pytest.mark.asyncio
    async def test_search_products_with_filters(self, repository, sample_products):
        """Test product search with additional filters."""
        filters = ProductSearchFilters(active=True)
        products = await repository.search_products("paper", filters=filters)
        
        # Should find active products containing "paper"
        assert len(products) == 2
        assert all(product.active for product in products)

    @pytest.mark.asyncio
    async def test_search_products_relevance_scoring(self, repository, sample_products):
        """Test that search results are ordered by relevance."""
        # Add a product with exact name match
        exact_match = Product(
            id="4",
            name="crane",  # Exact match for "crane" search
            description="Exact match product",
            active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        repository.add_test_product(exact_match)
        
        products = await repository.search_products("crane")
        
        # Exact match should come first
        assert len(products) == 2
        assert products[0].name == "crane"  # Exact match first
        assert products[1].name == "Origami Crane"  # Partial match second

    @pytest.mark.asyncio
    async def test_get_featured_products(self, repository, sample_products):
        """Test retrieving featured products."""
        products = await repository.get_featured_products()
        
        # Should return only featured and active products
        assert len(products) == 1
        assert products[0].name == "Origami Crane"
        assert products[0].featured is True
        assert products[0].active is True

    @pytest.mark.asyncio
    async def test_get_products_by_category(self, repository, sample_products):
        """Test retrieving products by category."""
        products = await repository.get_products_by_category("origami")
        
        # Should return only active origami products
        assert len(products) == 2
        assert all(product.category == "origami" for product in products)
        assert all(product.active for product in products)

    @pytest.mark.asyncio
    async def test_count_products(self, repository, sample_products):
        """Test counting products."""
        # Count all products
        total_count = await repository.count_products()
        assert total_count == 3
        
        # Count active products only
        active_filters = ProductSearchFilters(active=True)
        active_count = await repository.count_products(active_filters)
        assert active_count == 2

    @pytest.mark.asyncio
    async def test_failure_mode(self, repository, sample_products):
        """Test repository failure mode simulation."""
        # Enable failure mode
        repository.set_failure_mode(True, "Simulated database failure")
        
        # All operations should fail
        with pytest.raises(RepositoryError) as exc_info:
            await repository.get_all_products()
        assert "Simulated database failure" in str(exc_info.value)
        
        with pytest.raises(RepositoryError):
            await repository.get_product_by_id("1")
        
        with pytest.raises(RepositoryError):
            await repository.create_product(ProductCreate(name="Test"))
        
        # Disable failure mode
        repository.set_failure_mode(False)
        
        # Operations should work again
        products = await repository.get_all_products()
        assert len(products) == 3

    def test_helper_methods(self, repository, sample_products):
        """Test helper methods for testing."""
        # Test product count
        assert repository.get_product_count() == 3
        
        # Test getting all IDs
        ids = repository.get_all_product_ids()
        assert set(ids) == {"1", "2", "3"}
        
        # Test clearing products
        repository.clear_all_products()
        assert repository.get_product_count() == 0
        assert repository.get_all_product_ids() == []

    @pytest.mark.asyncio
    async def test_complex_filter_combinations(self, repository, sample_products):
        """Test complex combinations of filters."""
        filters = ProductSearchFilters(
            active=True,
            category="origami",
            min_price=10.0,
            max_price=20.0,
            tags=["paper"]
        )
        
        products = await repository.get_all_products(filters=filters)
        
        # Should match both origami products (both are active, in price range, and have "paper" tag)
        assert len(products) == 2
        for product in products:
            assert product.active is True
            assert product.category == "origami"
            assert 10.0 <= product.price <= 20.0
            assert "paper" in product.tags

    @pytest.mark.asyncio
    async def test_in_stock_filter(self, repository, sample_products):
        """Test in-stock filter functionality."""
        # Test in-stock filter (inventory > 0)
        in_stock_filters = ProductSearchFilters(in_stock=True)
        in_stock_products = await repository.get_all_products(filters=in_stock_filters)
        
        # Should return products with inventory > 0
        assert len(in_stock_products) == 2
        for product in in_stock_products:
            assert product.inventory_count > 0
        
        # Test out-of-stock filter (inventory <= 0 or None)
        out_of_stock_filters = ProductSearchFilters(in_stock=False)
        out_of_stock_products = await repository.get_all_products(filters=out_of_stock_filters)
        
        # Should return products with inventory <= 0
        assert len(out_of_stock_products) == 1
        assert out_of_stock_products[0].inventory_count == 0