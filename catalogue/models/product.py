"""
Product data models for the Catalogue Service

This module defines the Product model with validation using Pydantic,
designed for MongoDB document storage with flexible attributes.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Annotated
from pydantic import BaseModel, Field, field_validator, ConfigDict
from pydantic_core import core_schema
from bson import ObjectId


class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic models."""
    
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        return core_schema.no_info_plain_validator_function(cls.validate)

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise ValueError("Invalid ObjectId")

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")
        return field_schema


class Product(BaseModel):
    """
    Product model with flexible attributes for MongoDB storage.
    
    This model supports both structured product data and flexible
    attributes for different product types.
    """
    
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    name: str = Field(..., min_length=1, max_length=255, description="Product name")
    description: Optional[str] = Field(None, max_length=2000, description="Product description")
    image_url: Optional[str] = Field(None, description="URL to product image")
    price: Optional[float] = Field(None, ge=0, description="Product price")
    category: Optional[str] = Field(None, max_length=100, description="Product category")
    tags: List[str] = Field(default_factory=list, description="Product tags for search")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Flexible product attributes")
    active: bool = Field(default=True, description="Whether the product is active")
    featured: bool = Field(default=False, description="Whether the product is featured")
    inventory_count: Optional[int] = Field(None, ge=0, description="Available inventory count")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "name": "Origami Crane",
                "description": "Beautiful origami crane made from premium paper",
                "image_url": "/static/images/origami/001-origami.png",
                "price": 15.99,
                "category": "origami",
                "tags": ["paper", "craft", "decoration"],
                "attributes": {
                    "difficulty": "intermediate",
                    "material": "paper",
                    "color": "pink"
                },
                "active": True,
                "featured": False,
                "inventory_count": 50
            }
        }
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate product name."""
        if not v or not v.strip():
            raise ValueError('Product name cannot be empty')
        return v.strip()

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        """Validate and clean tags."""
        if v is None:
            return []
        # Remove empty tags and convert to lowercase
        return [tag.lower().strip() for tag in v if tag and tag.strip()]

    @field_validator('updated_at', mode='before')
    @classmethod
    def set_updated_at(cls, v):
        """Always set updated_at to current time."""
        return datetime.utcnow()

    def dict(self, **kwargs):
        """Override dict method to handle ObjectId serialization."""
        d = super().dict(**kwargs)
        if "_id" in d and d["_id"] is not None:
            d["_id"] = str(d["_id"])
        return d


class ProductCreate(BaseModel):
    """Model for creating new products."""
    
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    image_url: Optional[str] = None
    price: Optional[float] = Field(None, ge=0)
    category: Optional[str] = Field(None, max_length=100)
    tags: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    active: bool = Field(default=True)
    featured: bool = Field(default=False)
    inventory_count: Optional[int] = Field(None, ge=0)


class ProductUpdate(BaseModel):
    """Model for updating existing products."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    image_url: Optional[str] = None
    price: Optional[float] = Field(None, ge=0)
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = None
    attributes: Optional[Dict[str, Any]] = None
    active: Optional[bool] = None
    featured: Optional[bool] = None
    inventory_count: Optional[int] = Field(None, ge=0)


class ProductSearchFilters(BaseModel):
    """Model for product search filters."""
    
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    active: Optional[bool] = True
    featured: Optional[bool] = None
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    in_stock: Optional[bool] = None  # Filter for products with inventory > 0

    @field_validator('max_price')
    @classmethod
    def validate_price_range(cls, v, info):
        """Validate that max_price is greater than min_price."""
        if v is not None and info.data.get('min_price') is not None:
            if v < info.data['min_price']:
                raise ValueError('max_price must be greater than or equal to min_price')
        return v