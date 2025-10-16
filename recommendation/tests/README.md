# Redis Operations Unit Tests

This document describes the comprehensive unit tests implemented for Redis operations in the recommendation service.

## Overview

The Redis operations tests validate the caching functionality, TTL management, cache invalidation, and fallback behavior of the Enhanced Redis Repository. These tests ensure that the Redis-based caching system works correctly under various conditions including normal operations, error scenarios, and concurrent access.

## Test Structure

### Test Suite: `RedisOperationsTestSuite`

The main test suite uses `testify/suite` to provide setup and teardown functionality with a real Redis instance (via miniredis) for integration-style testing.

#### Setup

- **Mini Redis**: Uses `miniredis` to provide a real Redis instance for testing
- **Test Repository**: Creates a repository instance using `NewTestEnhancedRedisRepository`
- **Clean State**: Each test starts with a fresh Redis instance (FlushAll)

### Test Categories

#### 1. Cache Functionality Tests

**TestRedisCaching_Success**

- Validates basic caching behavior
- Ensures first call caches data and second call returns cached result
- Verifies cache keys are created correctly

**TestRedisCaching_TTLExpiration**

- Tests TTL (Time To Live) functionality
- Uses miniredis FastForward to simulate time passage
- Verifies expired cache entries are properly removed

**TestOrigamiOfTheDay_Caching**

- Tests daily origami caching with date-based keys
- Validates TTL is set until end of day
- Ensures consistent results within the same day

#### 2. Cache Invalidation Tests

**TestCacheInvalidation_UserSpecific**

- Tests selective cache invalidation for specific users
- Verifies other users' caches remain intact
- Validates pattern-based key deletion

**TestCacheInvalidation_AllRecommendations**

- Tests global cache invalidation
- Verifies all recommendation-related caches are cleared
- Tests multiple cache patterns simultaneously

#### 3. Scoring and Ranking Tests

**TestScoreOperations_UpdateAndRetrieve**

- Tests individual score updates
- Validates score storage in Redis sorted sets
- Tests top-rated retrieval with correct ordering

**TestScoreOperations_BatchUpdate**

- Tests batch score updates using Redis pipelines
- Validates score history tracking
- Ensures atomic batch operations

#### 4. Personalization Tests

**TestPersonalizedRecommendations_Caching**

- Tests personalized recommendation caching
- Validates preference-based cache keys
- Tests user preference storage

#### 5. Cache Management Tests

**TestCacheWarmup_Success**

- Tests cache warming functionality
- Validates pre-loading of frequently accessed data
- Ensures cache entries are created proactively

**TestUserCacheWarmup_Success**

- Tests user-specific cache warming
- Validates user activity tracking
- Tests personalized cache pre-loading

#### 6. Performance and Monitoring Tests

**TestCacheStats_Accuracy**

- Tests cache statistics collection
- Validates hit rate calculations
- Tests pool statistics reporting

**TestUserEngagementTracking**

- Tests user activity tracking
- Validates engagement metrics collection
- Tests activity data persistence

#### 7. Error Handling and Resilience Tests

**TestFallbackBehavior_RedisUnavailable**

- Tests behavior when Redis is unavailable
- Validates graceful error handling
- Tests system resilience to cache failures

**TestHealthCheck_Success**

- Tests health check functionality
- Validates connection status reporting
- Tests response time measurement

#### 8. Concurrency and Data Consistency Tests

**TestConcurrentOperations_ThreadSafety**

- Tests concurrent access to cache operations
- Validates thread safety of repository operations
- Tests data integrity under concurrent load

**TestDataConsistency_MultipleUpdates**

- Tests data consistency with multiple updates
- Validates score history tracking
- Tests final state correctness

### Individual Unit Tests

#### Validation Function Tests

**TestValidationFunctions**

- Tests user ID validation (empty, whitespace)
- Tests score validation (range 0-10)
- Tests error message accuracy

#### TTL Functionality Tests

**TestCacheTTLFunctionality**

- Tests recommendation cache TTL settings
- Tests origami of the day TTL (until end of day)
- Validates TTL values are within expected ranges

#### Batch Operations Tests

**TestBatchOperations**

- Tests batch score updates
- Tests batch user cache invalidation
- Validates atomic batch operations

## Key Features Tested

### 1. Caching with Mock Redis

- Uses `miniredis` for realistic Redis behavior
- Tests actual Redis commands and responses
- Validates cache key patterns and TTL settings

### 2. Cache Invalidation and TTL

- Tests selective and global cache invalidation
- Validates TTL functionality with time simulation
- Tests cache expiration behavior

### 3. Fallback Behavior

- Tests graceful degradation when Redis is unavailable
- Validates error handling and logging
- Tests system resilience

### 4. Concurrent Operations

- Tests thread safety with goroutines
- Validates data integrity under concurrent access
- Tests race condition handling

### 5. Data Consistency

- Tests score updates and history tracking
- Validates final state after multiple operations
- Tests atomic operations

## Test Utilities

### Mock Redis Manager

The tests use a simplified Redis manager that provides direct access to the Redis client for testing purposes.

### Test Repository Constructor

`NewTestEnhancedRedisRepository` creates a repository instance specifically for testing, bypassing production dependencies.

### Miniredis Features Used

- **FlushAll**: Clears all data between tests
- **FastForward**: Simulates time passage for TTL testing
- **Real Redis Commands**: Provides authentic Redis behavior

## Requirements Coverage

The tests cover all requirements specified in task 5.4:

✅ **Create unit tests for recommendation caching with mock Redis**

- Comprehensive caching tests with miniredis
- Mock Redis behavior for various scenarios

✅ **Test cache invalidation and TTL functionality**

- Multiple invalidation scenarios (user-specific, global)
- TTL testing with time simulation
- Cache expiration validation

✅ **Validate fallback behavior when cache is unavailable**

- Redis unavailability simulation
- Graceful error handling tests
- System resilience validation

## Running the Tests

```bash
# Run all Redis operation tests
go test ./tests -v -run TestRedisOperationsTestSuite

# Run all tests including individual unit tests
go test ./tests -v

# Run specific test categories
go test ./tests -v -run TestValidationFunctions
go test ./tests -v -run TestCacheTTLFunctionality
go test ./tests -v -run TestBatchOperations
```

## Test Coverage

The tests provide comprehensive coverage of:

- ✅ Cache operations (GET, SET, DEL)
- ✅ TTL management and expiration
- ✅ Cache invalidation patterns
- ✅ Score operations and sorted sets
- ✅ User engagement tracking
- ✅ Batch operations and pipelines
- ✅ Error handling and fallbacks
- ✅ Concurrent access and thread safety
- ✅ Health checks and monitoring
- ✅ Data consistency and integrity

This test suite ensures the Redis operations are robust, performant, and reliable under various conditions.
