"""Database package for catalogue service."""

from .connection_manager import MongoDBConnectionManager, create_connection_manager

__all__ = ['MongoDBConnectionManager', 'create_connection_manager']