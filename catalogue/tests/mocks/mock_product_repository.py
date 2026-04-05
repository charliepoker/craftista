"""
Mock implementation of ProductRepository for fast unit testing.

This module provides a mock repository that implements the ProductRepository
interface using in-memory data structures for testing purposes.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from models.product import Product, ProductCreate, ProductUpdate, ProductSearchFilters
from repository.base import ProductRepository, RepositoryError, ValidationError


class MockProductRepository(ProductRepository):
    """
    Mock implementation of ProductRepository using in-memory storage.
    
    This mock repository provides all the functionality of a real repository
    but stores data in memory for fast, isolated testing.
    """

    def __init__(self):
        """Initialize the mock repository with empty data."""
        self._products: Dict[str, Product] = {}
        self._next_id = 1
        self._should_fail = False
        self._failure_message = "Mock repository failure"

    def set_failure_mode(self, should_fail: bool, message: str = "Mock repository failure"):
        """
        Configure the mock to simulate failures.
        
        Args:
            should_fail: Whether operations should fail
            message: Error message to use for failures
        """
        self._should_fail = should_fail
        self._failure_message = message

    def _check_failure(self):
        """Check if operation should fail and raise error if configured to do so."""
        if self._should_fail:
            raise RepositoryError(self._failure_message)

    def _generate_id(self) -> str:
        """Generate a new unique ID in valid ObjectId format (24 hex chars)."""
        product_id = format(self._next_id, '024x')
        self._next_id += 1
        return product_id

    def _matches_filters(self, product: Product, filters: Optional[ProductSearchFilters]) -> bool:
        """Check if a product matches the given filters."""
        if not filters:
            return True

        # Active status filter
        if filters.active is not None and product.active != filters.active:
            return False

        # Category filter
        if filters.category and product.category:
            if product.category.lower() != filters.category.lower():
                return False

        # Tags filter (product must have at least one matching tag)
        if filters.tags:
            filter_tags = [tag.lower() for tag in filters.tags]
            product_tags = [tag.lower() for tag in product.tags]
            if not any(tag in product_tags for tag in filter_tags):
                return False

        # Featured filter
        if filters.featured is not None and product.featured != filters.featured:
            return False

        # Price range filters
        if filters.min_price is not None and product.price is not None:
            if product.price < filters.min_price:
                return False

        if filters.max_price is not None and product.price is not None:
            if product.price > filters.max_price:
                return False

        # In stock filter
        if filters.in_stock is not None:
            if filters.in_stock:
                # Must have inventory > 0
                if product.inventory_count is None or product.inventory_count <= 0:
                    return False
            else:
                # Must have inventory <= 0 or None
                if product.inventory_count is not None and product.inventory_count > 0:
                    return False

        return True

    def _matches_search_query(self, product: Product, query: str) -> bool:
        """Check if a product matches the search query."""
        query_lower = query.lower()
        
        # Search in name
        if product.name and query_lower in product.name.lower():
            return True
        
        # Search in description
        if product.description and query_lower in product.description.lower():
            return True
        
        # Search in tags
        for tag in product.tags:
            if query_lower in tag.lower():
                return True
        
        return False

    async def get_all_products(self, filters: Optional[ProductSearchFilters] = None, 
                              skip: int = 0, limit: int = 100) -> List[Product]:
        """Retrieve all products with optional filtering and pagination."""
        self._check_failure()
        
        # Filter products
        filtered_products = [
            product for product in self._products.values()
            if self._matches_filters(product, filters)
        ]
        
        # Sort by created_at descending (newest first)
        filtered_products.sort(key=lambda p: p.created_at, reverse=True)
        
        # Apply pagination
        end_index = skip + limit
        return filtered_products[skip:end_index]

    async def get_product_by_id(self, product_id: str) -> Optional[Product]:
        """Retrieve a single product by its ID."""
        self._check_failure()
        return self._products.get(product_id)

    async def create_product(self, product_data: ProductCreate) -> Product:
        """Create a new product."""
        self._check_failure()
        
        # Validate data
        if product_data.price is not None and product_data.price < 0:
            raise ValidationError("Price cannot be negative")
        
        if product_data.inventory_count is not None and product_data.inventory_count < 0:
            raise ValidationError("Inventory count cannot be negative")
        
        if not product_data.name or not product_data.name.strip():
            raise ValidationError("Product name cannot be empty")
        
        # Generate ID and create product
        product_id = self._generate_id()
        now = datetime.utcnow()
        
        # Clean tags
        clean_tags = []
        if product_data.tags:
            clean_tags = [tag.lower().strip() for tag in product_data.tags if tag.strip()]
            clean_tags = list(set(clean_tags))  # Remove duplicates
        
        product = Product(
            id=product_id,
            name=product_data.name.strip(),
            description=product_data.description,
            image_url=product_data.image_url,
            price=product_data.price,
            category=product_data.category,
            tags=clean_tags,
            attributes=product_data.attributes or {},
            active=product_data.active,
            featured=product_data.featured,
            inventory_count=product_data.inventory_count,
            created_at=now,
            updated_at=now
        )
        
        self._products[product_id] = product
        return product

    async def update_product(self, product_id: str, updates: ProductUpdate) -> Optional[Product]:
        """Update an existing product."""
        self._check_failure()
        
        product = self._products.get(product_id)
        if not product:
            return None
        
        # Validate updates
        if updates.price is not None and updates.price < 0:
            raise ValidationError("Price cannot be negative")
        
        if updates.inventory_count is not None and updates.inventory_count < 0:
            raise ValidationError("Inventory count cannot be negative")
        
        if updates.name is not None and (not updates.name or not updates.name.strip()):
            raise ValidationError("Product name cannot be empty")
        
        # Apply updates
        update_data = updates.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            if field == "tags" and value is not None:
                # Clean tags
                clean_tags = [tag.lower().strip() for tag in value if tag.strip()]
                clean_tags = list(set(clean_tags))  # Remove duplicates
                setattr(product, field, clean_tags)
            elif field == "name" and value is not None:
                setattr(product, field, value.strip())
            else:
                setattr(product, field, value)
        
        # Update timestamp
        product.updated_at = datetime.utcnow()
        
        return product

    async def delete_product(self, product_id: str) -> bool:
        """Delete a product by its ID."""
        self._check_failure()
        
        if product_id in self._products:
            del self._products[product_id]
            return True
        return False

    async def search_products(self, query: str, filters: Optional[ProductSearchFilters] = None,
                             skip: int = 0, limit: int = 100) -> List[Product]:
        """Search products using text search with optional filters."""
        self._check_failure()
        
        # Filter products by search query and filters
        matching_products = []
        for product in self._products.values():
            if (self._matches_search_query(product, query) and 
                self._matches_filters(product, filters)):
                matching_products.append(product)
        
        # Sort by relevance (simple: exact name matches first, then others)
        query_lower = query.lower()
        
        def relevance_score(product):
            score = 0
            if product.name and query_lower in product.name.lower():
                if product.name.lower() == query_lower:
                    score += 100  # Exact match
                elif product.name.lower().startswith(query_lower):
                    score += 50   # Starts with query
                else:
                    score += 25   # Contains query
            
            if product.description and query_lower in product.description.lower():
                score += 10
            
            for tag in product.tags:
                if query_lower in tag.lower():
                    score += 5
            
            return score
        
        matching_products.sort(key=relevance_score, reverse=True)
        
        # Apply pagination
        end_index = skip + limit
        return matching_products[skip:end_index]

    async def get_featured_products(self, limit: int = 10) -> List[Product]:
        """Retrieve featured products."""
        self._check_failure()
        
        featured_products = [
            product for product in self._products.values()
            if product.featured and product.active
        ]
        
        # Sort by created_at descending
        featured_products.sort(key=lambda p: p.created_at, reverse=True)
        
        return featured_products[:limit]

    async def get_products_by_category(self, category: str, skip: int = 0, 
                                      limit: int = 100) -> List[Product]:
        """Retrieve products by category with pagination."""
        self._check_failure()
        
        category_products = [
            product for product in self._products.values()
            if (product.category and 
                product.category.lower() == category.lower() and 
                product.active)
        ]
        
        # Sort by created_at descending
        category_products.sort(key=lambda p: p.created_at, reverse=True)
        
        # Apply pagination
        end_index = skip + limit
        return category_products[skip:end_index]

    async def count_products(self, filters: Optional[ProductSearchFilters] = None) -> int:
        """Count total number of products matching filters."""
        self._check_failure()
        
        count = 0
        for product in self._products.values():
            if self._matches_filters(product, filters):
                count += 1
        
        return count

    # Additional helper methods for testing

    def add_test_product(self, product: Product) -> None:
        """Add a product directly for testing purposes."""
        if not product.id:
            product.id = self._generate_id()
        self._products[str(product.id)] = product

    def clear_all_products(self) -> None:
        """Clear all products from the mock repository."""
        self._products.clear()
        self._next_id = 1

    def get_product_count(self) -> int:
        """Get the total number of products in the repository."""
        return len(self._products)

    def get_all_product_ids(self) -> List[str]:
        """Get all product IDs in the repository."""
        return list(self._products.keys())