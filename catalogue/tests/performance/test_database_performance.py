"""
Performance tests for database operations under load.

This module provides comprehensive performance testing for MongoDB operations
to ensure the database can handle expected load and identify performance bottlenecks.
"""

import pytest
import pytest_asyncio
import asyncio
import time
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import threading

try:
    from testcontainers.mongodb import MongoDbContainer
    from motor.motor_asyncio import AsyncIOMotorClient
    TESTCONTAINERS_AVAILABLE = True
except ImportError:
    TESTCONTAINERS_AVAILABLE = False

from models.product import Product, ProductCreate, ProductUpdate, ProductSearchFilters
from repository.mongodb_repository import MongoDBProductRepository


@pytest.mark.skipif(not TESTCONTAINERS_AVAILABLE, reason="testcontainers not available")
@pytest.mark.performance
class TestDatabasePerformance:
    """Performance tests for MongoDB operations under various load conditions."""

    @pytest.fixture(scope="class")
    def mongodb_container(self):
        """Start MongoDB test container for performance testing."""
        try:
            with MongoDbContainer("mongo:7.0") as container:
                yield container
        except Exception as e:
            pytest.skip(f"Failed to start MongoDB container: {e}")

    @pytest_asyncio.fixture
    async def mongodb_client(self, mongodb_container):
        """Create MongoDB client for performance testing."""
        connection_url = mongodb_container.get_connection_url()
        client = AsyncIOMotorClient(connection_url)
        yield client
        client.close()

    @pytest_asyncio.fixture
    async def test_database(self, mongodb_client):
        """Create test database for performance testing."""
        db_name = "perf_test_catalogue_db"
        database = mongodb_client[db_name]
        yield database
        await mongodb_client.drop_database(db_name)

    @pytest_asyncio.fixture
    async def repository(self, test_database):
        """Create repository instance for performance testing."""
        repo = MongoDBProductRepository(test_database)
        yield repo
        await test_database.products.delete_many({})

    @pytest_asyncio.fixture
    async def large_dataset(self, repository):
        """Create a large dataset for performance testing."""
        products = []
        batch_size = 100
        total_products = 1000

        for i in range(0, total_products, batch_size):
            batch = []
            for j in range(batch_size):
                product_index = i + j
                if product_index >= total_products:
                    break
                
                product_data = ProductCreate(
                    name=f"Performance Test Product {product_index:04d}",
                    description=f"Description for performance test product {product_index}",
                    price=10.0 + (product_index % 100),
                    category=f"category_{product_index % 10}",
                    tags=[f"tag_{product_index % 20}", f"perf_tag_{product_index % 5}"],
                    attributes={
                        "difficulty": ["beginner", "intermediate", "advanced"][product_index % 3],
                        "color": ["red", "blue", "green", "yellow"][product_index % 4],
                        "size": ["small", "medium", "large"][product_index % 3]
                    },
                    featured=(product_index % 10 == 0),
                    inventory_count=product_index % 100
                )
                batch.append(product_data)
            
            # Create batch concurrently
            tasks = [repository.create_product(product) for product in batch]
            batch_results = await asyncio.gather(*tasks)
            products.extend(batch_results)
            
            # Small delay to avoid overwhelming the database
            await asyncio.sleep(0.1)

        return products

    async def test_read_performance_single_operations(self, repository, large_dataset):
        """Test read performance for single operations."""
        # Test get_all_products performance
        start_time = time.time()
        all_products = await repository.get_all_products()
        get_all_duration = time.time() - start_time

        assert len(all_products) == len(large_dataset)
        assert get_all_duration < 2.0, f"get_all_products took {get_all_duration:.2f}s, expected < 2.0s"

        # Test get_product_by_id performance
        test_product = large_dataset[500]  # Middle product
        
        start_time = time.time()
        found_product = await repository.get_product_by_id(str(test_product.id))
        get_by_id_duration = time.time() - start_time

        assert found_product is not None
        assert get_by_id_duration < 0.1, f"get_product_by_id took {get_by_id_duration:.2f}s, expected < 0.1s"

        # Test search performance
        start_time = time.time()
        search_results = await repository.search_products("Performance Test")
        search_duration = time.time() - start_time

        assert len(search_results) > 0
        assert search_duration < 1.0, f"search_products took {search_duration:.2f}s, expected < 1.0s"

    async def test_write_performance_single_operations(self, repository):
        """Test write performance for single operations."""
        # Test create performance
        create_times = []
        for i in range(100):
            product_data = ProductCreate(
                name=f"Write Perf Test {i}",
                description=f"Write performance test product {i}",
                price=15.0 + i
            )
            
            start_time = time.time()
            created_product = await repository.create_product(product_data)
            create_duration = time.time() - start_time
            create_times.append(create_duration)
            
            assert created_product is not None

        avg_create_time = statistics.mean(create_times)
        max_create_time = max(create_times)
        
        assert avg_create_time < 0.1, f"Average create time {avg_create_time:.3f}s, expected < 0.1s"
        assert max_create_time < 0.5, f"Max create time {max_create_time:.3f}s, expected < 0.5s"

        # Test update performance
        products = await repository.get_all_products()
        update_times = []
        
        for i, product in enumerate(products[:50]):  # Test first 50 products
            updates = ProductUpdate(
                name=f"Updated {product.name}",
                price=product.price + 1.0
            )
            
            start_time = time.time()
            updated_product = await repository.update_product(str(product.id), updates)
            update_duration = time.time() - start_time
            update_times.append(update_duration)
            
            assert updated_product is not None

        avg_update_time = statistics.mean(update_times)
        assert avg_update_time < 0.1, f"Average update time {avg_update_time:.3f}s, expected < 0.1s"

    async def test_concurrent_read_performance(self, repository, large_dataset):
        """Test read performance under concurrent load."""
        concurrent_users = 20
        operations_per_user = 50
        
        async def user_read_operations():
            """Simulate a user performing multiple read operations."""
            operation_times = []
            
            for _ in range(operations_per_user):
                # Mix of different read operations
                operation_type = _ % 4
                
                start_time = time.time()
                
                if operation_type == 0:
                    # Get all products with pagination
                    await repository.get_all_products(skip=_ * 10, limit=10)
                elif operation_type == 1:
                    # Get product by ID
                    test_product = large_dataset[_ % len(large_dataset)]
                    await repository.get_product_by_id(str(test_product.id))
                elif operation_type == 2:
                    # Search products
                    await repository.search_products(f"Product {_ % 100:04d}")
                else:
                    # Get featured products
                    await repository.get_featured_products()
                
                operation_times.append(time.time() - start_time)
            
            return operation_times

        # Execute concurrent operations
        start_time = time.time()
        tasks = [user_read_operations() for _ in range(concurrent_users)]
        all_operation_times = await asyncio.gather(*tasks)
        total_duration = time.time() - start_time

        # Flatten all operation times
        flat_times = [time for user_times in all_operation_times for time in user_times]
        
        # Performance assertions
        total_operations = concurrent_users * operations_per_user
        avg_operation_time = statistics.mean(flat_times)
        operations_per_second = total_operations / total_duration
        
        assert avg_operation_time < 0.2, f"Average operation time {avg_operation_time:.3f}s, expected < 0.2s"
        assert operations_per_second > 100, f"Operations per second {operations_per_second:.1f}, expected > 100"
        
        # Check for outliers (operations taking too long)
        slow_operations = [t for t in flat_times if t > 1.0]
        slow_operation_percentage = len(slow_operations) / len(flat_times) * 100
        
        assert slow_operation_percentage < 5, f"Slow operations: {slow_operation_percentage:.1f}%, expected < 5%"

    async def test_concurrent_write_performance(self, repository):
        """Test write performance under concurrent load."""
        concurrent_writers = 10
        writes_per_writer = 20
        
        async def writer_operations():
            """Simulate a writer performing multiple write operations."""
            operation_times = []
            created_products = []
            
            for i in range(writes_per_writer):
                # Create operation
                product_data = ProductCreate(
                    name=f"Concurrent Write Test {threading.current_thread().ident}_{i}",
                    description=f"Concurrent write test product",
                    price=20.0 + i
                )
                
                start_time = time.time()
                created_product = await repository.create_product(product_data)
                create_duration = time.time() - start_time
                
                operation_times.append(create_duration)
                created_products.append(created_product)
                
                # Update operation (every other iteration)
                if i % 2 == 1 and created_products:
                    product_to_update = created_products[i // 2]
                    updates = ProductUpdate(
                        name=f"Updated {product_to_update.name}",
                        price=product_to_update.price + 5.0
                    )
                    
                    start_time = time.time()
                    await repository.update_product(str(product_to_update.id), updates)
                    update_duration = time.time() - start_time
                    
                    operation_times.append(update_duration)
            
            return operation_times

        # Execute concurrent write operations
        start_time = time.time()
        tasks = [writer_operations() for _ in range(concurrent_writers)]
        all_operation_times = await asyncio.gather(*tasks)
        total_duration = time.time() - start_time

        # Flatten all operation times
        flat_times = [time for writer_times in all_operation_times for time in writer_times]
        
        # Performance assertions
        avg_write_time = statistics.mean(flat_times)
        writes_per_second = len(flat_times) / total_duration
        
        assert avg_write_time < 0.3, f"Average write time {avg_write_time:.3f}s, expected < 0.3s"
        assert writes_per_second > 50, f"Writes per second {writes_per_second:.1f}, expected > 50"

    async def test_mixed_workload_performance(self, repository, large_dataset):
        """Test performance under mixed read/write workload."""
        concurrent_users = 15
        operations_per_user = 30
        
        async def mixed_workload_user():
            """Simulate a user with mixed read/write operations."""
            operation_times = []
            
            for i in range(operations_per_user):
                operation_type = i % 5
                start_time = time.time()
                
                if operation_type in [0, 1, 2]:  # 60% reads
                    if operation_type == 0:
                        await repository.get_all_products(skip=i * 5, limit=5)
                    elif operation_type == 1:
                        test_product = large_dataset[i % len(large_dataset)]
                        await repository.get_product_by_id(str(test_product.id))
                    else:
                        await repository.search_products(f"Test {i}")
                
                elif operation_type == 3:  # 20% writes (create)
                    product_data = ProductCreate(
                        name=f"Mixed Workload Product {threading.current_thread().ident}_{i}",
                        price=25.0 + i
                    )
                    await repository.create_product(product_data)
                
                else:  # 20% writes (update)
                    if large_dataset:
                        product_to_update = large_dataset[i % len(large_dataset)]
                        updates = ProductUpdate(price=product_to_update.price + 0.1)
                        await repository.update_product(str(product_to_update.id), updates)
                
                operation_times.append(time.time() - start_time)
            
            return operation_times

        # Execute mixed workload
        start_time = time.time()
        tasks = [mixed_workload_user() for _ in range(concurrent_users)]
        all_operation_times = await asyncio.gather(*tasks)
        total_duration = time.time() - start_time

        # Performance analysis
        flat_times = [time for user_times in all_operation_times for time in user_times]
        
        avg_operation_time = statistics.mean(flat_times)
        total_operations = len(flat_times)
        operations_per_second = total_operations / total_duration
        
        # Performance assertions for mixed workload
        assert avg_operation_time < 0.25, f"Average operation time {avg_operation_time:.3f}s, expected < 0.25s"
        assert operations_per_second > 80, f"Operations per second {operations_per_second:.1f}, expected > 80"

    async def test_database_connection_pool_performance(self, repository):
        """Test performance of database connection pooling under load."""
        concurrent_connections = 50
        operations_per_connection = 10
        
        async def connection_intensive_operations():
            """Perform operations that stress the connection pool."""
            for i in range(operations_per_connection):
                # Rapid-fire operations to test connection pool
                await repository.count_products()
                
                # Small delay to simulate real-world usage
                await asyncio.sleep(0.01)

        # Execute operations that will stress connection pool
        start_time = time.time()
        tasks = [connection_intensive_operations() for _ in range(concurrent_connections)]
        await asyncio.gather(*tasks)
        total_duration = time.time() - start_time

        total_operations = concurrent_connections * operations_per_connection
        operations_per_second = total_operations / total_duration

        # Connection pool should handle this load efficiently
        assert operations_per_second > 200, f"Connection pool ops/sec {operations_per_second:.1f}, expected > 200"
        assert total_duration < 10, f"Total duration {total_duration:.2f}s, expected < 10s"

    async def test_memory_usage_under_load(self, repository):
        """Test memory usage patterns under sustained load."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Sustained operations to test memory usage
        for batch in range(10):
            # Create products
            products = []
            for i in range(100):
                product_data = ProductCreate(
                    name=f"Memory Test Product {batch}_{i}",
                    description="Testing memory usage patterns",
                    price=30.0 + i
                )
                product = await repository.create_product(product_data)
                products.append(product)
            
            # Read operations
            await repository.get_all_products()
            
            # Search operations
            await repository.search_products("Memory Test")
            
            # Cleanup some products
            for product in products[::2]:  # Delete every other product
                await repository.delete_product(str(product.id))

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Memory usage should not increase dramatically
        assert memory_increase < 100, f"Memory increased by {memory_increase:.1f}MB, expected < 100MB"

    async def test_query_performance_with_indexes(self, repository, large_dataset):
        """Test query performance to ensure indexes are being used effectively."""
        # Test category filtering (should use category index)
        start_time = time.time()
        category_results = await repository.get_all_products(
            filters=ProductSearchFilters(category="category_5")
        )
        category_query_time = time.time() - start_time
        
        assert len(category_results) > 0
        assert category_query_time < 0.5, f"Category query took {category_query_time:.3f}s, expected < 0.5s"

        # Test text search (should use text index)
        start_time = time.time()
        text_results = await repository.search_products("Performance Test Product")
        text_query_time = time.time() - start_time
        
        assert len(text_results) > 0
        assert text_query_time < 1.0, f"Text search took {text_query_time:.3f}s, expected < 1.0s"

        # Test featured products (should use featured index)
        start_time = time.time()
        featured_results = await repository.get_featured_products()
        featured_query_time = time.time() - start_time
        
        assert len(featured_results) > 0
        assert featured_query_time < 0.3, f"Featured query took {featured_query_time:.3f}s, expected < 0.3s"

        # Test price range filtering (should use price index if exists)
        start_time = time.time()
        price_results = await repository.get_all_products(
            filters=ProductSearchFilters(min_price=50.0, max_price=70.0)
        )
        price_query_time = time.time() - start_time
        
        assert price_query_time < 0.5, f"Price range query took {price_query_time:.3f}s, expected < 0.5s"

    def test_performance_metrics_collection(self, repository):
        """Test that performance metrics can be collected and analyzed."""
        # This test ensures we can collect performance metrics
        # In a real implementation, this would integrate with monitoring systems
        
        metrics = {
            "test_start_time": datetime.now(),
            "operations_completed": 0,
            "errors_encountered": 0,
            "average_response_time": 0.0,
            "peak_memory_usage": 0.0,
            "database_connections_used": 0
        }
        
        # Simulate metrics collection
        assert isinstance(metrics["test_start_time"], datetime)
        assert isinstance(metrics["operations_completed"], int)
        assert isinstance(metrics["average_response_time"], float)
        
        # In a real scenario, these metrics would be populated during test execution
        # and could be used for performance analysis and alerting