"""
Abstract base repository interfaces for the Catalogue Service.

This module defines the abstract repository pattern interfaces that must be
implemented by concrete repository classes for different storage backends.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from models.product import Product, ProductCreate, ProductUpdate, ProductSearchFilters


class ProductRepository(ABC):
    """
    Abstract repository interface for Product operations.
    
    This interface defines the contract that all product repository
    implementations must follow, ensuring consistent data access patterns
    across different storage backends.
    """

    @abstractmethod
    async def get_all_products(self, filters: Optional[ProductSearchFilters] = None, 
                              skip: int = 0, limit: int = 100) -> List[Product]:
        """
        Retrieve all products with optional filtering and pagination.
        
        Args:
            filters: Optional search filters to apply
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            
        Returns:
            List of Product objects matching the criteria
            
        Raises:
            RepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def get_product_by_id(self, product_id: str) -> Optional[Product]:
        """
        Retrieve a single product by its ID.
        
        Args:
            product_id: Unique identifier for the product
            
        Returns:
            Product object if found, None otherwise
            
        Raises:
            RepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def create_product(self, product_data: ProductCreate) -> Product:
        """
        Create a new product.
        
        Args:
            product_data: Product creation data
            
        Returns:
            Created Product object with generated ID
            
        Raises:
            RepositoryError: If database operation fails
            ValidationError: If product data is invalid
        """
        pass

    @abstractmethod
    async def update_product(self, product_id: str, updates: ProductUpdate) -> Optional[Product]:
        """
        Update an existing product.
        
        Args:
            product_id: Unique identifier for the product
            updates: Product update data
            
        Returns:
            Updated Product object if found and updated, None if not found
            
        Raises:
            RepositoryError: If database operation fails
            ValidationError: If update data is invalid
        """
        pass

    @abstractmethod
    async def delete_product(self, product_id: str) -> bool:
        """
        Delete a product by its ID.
        
        Args:
            product_id: Unique identifier for the product
            
        Returns:
            True if product was deleted, False if not found
            
        Raises:
            RepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def search_products(self, query: str, filters: Optional[ProductSearchFilters] = None,
                             skip: int = 0, limit: int = 100) -> List[Product]:
        """
        Search products using text search with optional filters.
        
        Args:
            query: Text search query
            filters: Optional search filters to apply
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            
        Returns:
            List of Product objects matching the search criteria
            
        Raises:
            RepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def get_featured_products(self, limit: int = 10) -> List[Product]:
        """
        Retrieve featured products.
        
        Args:
            limit: Maximum number of featured products to return
            
        Returns:
            List of featured Product objects
            
        Raises:
            RepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def get_products_by_category(self, category: str, skip: int = 0, 
                                      limit: int = 100) -> List[Product]:
        """
        Retrieve products by category with pagination.
        
        Args:
            category: Product category to filter by
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return
            
        Returns:
            List of Product objects in the specified category
            
        Raises:
            RepositoryError: If database operation fails
        """
        pass

    @abstractmethod
    async def count_products(self, filters: Optional[ProductSearchFilters] = None) -> int:
        """
        Count total number of products matching filters.
        
        Args:
            filters: Optional search filters to apply
            
        Returns:
            Total count of products matching the criteria
            
        Raises:
            RepositoryError: If database operation fails
        """
        pass


class RepositoryError(Exception):
    """Base exception for repository operations."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error


class ValidationError(RepositoryError):
    """Exception raised when data validation fails."""
    pass


class ConnectionError(RepositoryError):
    """Exception raised when database connection fails."""
    pass