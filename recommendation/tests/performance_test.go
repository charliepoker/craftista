package tests

import (
	"context"
	"fmt"
	"recommendation/repository"
	"runtime"
	"sort"
	"sync"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/stretchr/testify/suite"
)

// PerformanceTestSuite provides comprehensive performance testing for Redis operations
type PerformanceTestSuite struct {
	suite.Suite
	miniRedis  *miniredis.Miniredis
	client     *redis.Client
	repository *repository.EnhancedRedisRepository
	ctx        context.Context
}

func (suite *PerformanceTestSuite) SetupSuite() {
	var err error
	suite.miniRedis, err = miniredis.Run()
	require.NoError(suite.T(), err)

	suite.client = redis.NewClient(&redis.Options{
		Addr:         suite.miniRedis.Addr(),
		PoolSize:     100, // Increase pool size for performance testing
		MinIdleConns: 10,
	})

	suite.ctx = context.Background()
}

func (suite *PerformanceTestSuite) SetupTest() {
	suite.miniRedis.FlushAll()
	suite.repository = repository.NewTestEnhancedRedisRepository(suite.client)
}

func (suite *PerformanceTestSuite) TearDownSuite() {
	if suite.client != nil {
		suite.client.Close()
	}
	if suite.miniRedis != nil {
		suite.miniRedis.Close()
	}
}

func (suite *PerformanceTestSuite) TestHighVolumeReadOperations() {
	// Setup: Create a large dataset
	numItems := 1000
	for i := 0; i < numItems; i++ {
		err := suite.repository.UpdateRecommendationScore(fmt.Sprintf("Item%d", i), float64(i%10))
		require.NoError(suite.T(), err)
	}

	// Warm cache with recommendations for multiple users
	for i := 0; i < 100; i++ {
		_, err := suite.repository.GetRecommendations(fmt.Sprintf("user%d", i), 5)
		require.NoError(suite.T(), err)
	}

	// Test: High volume read operations
	startTime := time.Now()
	numReads := 10000
	
	for i := 0; i < numReads; i++ {
		userID := fmt.Sprintf("user%d", i%100)
		_, err := suite.repository.GetRecommendations(userID, 5)
		assert.NoError(suite.T(), err)
	}
	
	duration := time.Since(startTime)
	readsPerSecond := float64(numReads) / duration.Seconds()

	// Performance assertions
	assert.Greater(suite.T(), readsPerSecond, 1000.0, "Should handle > 1000 reads/second")
	assert.Less(suite.T(), duration, 15*time.Second, "Should complete within 15 seconds")
}

func (suite *PerformanceTestSuite) TestConcurrentReadOperations() {
	// Setup: Create test data
	for i := 0; i < 100; i++ {
		err := suite.repository.UpdateRecommendationScore(fmt.Sprintf("ConcurrentItem%d", i), float64(i%10))
		require.NoError(suite.T(), err)
	}

	// Test: Concurrent read operations
	concurrentUsers := 50
	operationsPerUser := 100
	
	startTime := time.Now()
	
	var wg sync.WaitGroup
	errorChan := make(chan error, concurrentUsers*operationsPerUser)
	
	for user := 0; user < concurrentUsers; user++ {
		wg.Add(1)
		go func(userIndex int) {
			defer wg.Done()
			userID := fmt.Sprintf("concurrent_user_%d", userIndex)
			
			for op := 0; op < operationsPerUser; op++ {
				_, err := suite.repository.GetRecommendations(userID, 5)
				if err != nil {
					errorChan <- err
				}
			}
		}(user)
	}
	
	wg.Wait()
	close(errorChan)
	
	duration := time.Since(startTime)
	totalOperations := concurrentUsers * operationsPerUser
	operationsPerSecond := float64(totalOperations) / duration.Seconds()

	// Check for errors
	errorCount := 0
	for err := range errorChan {
		if err != nil {
			errorCount++
		}
	}

	// Performance assertions
	assert.Equal(suite.T(), 0, errorCount, "Should have no errors during concurrent operations")
	assert.Greater(suite.T(), operationsPerSecond, 500.0, "Should handle > 500 concurrent ops/second")
	assert.Less(suite.T(), duration, 20*time.Second, "Should complete within 20 seconds")
}

func (suite *PerformanceTestSuite) TestHighVolumeWriteOperations() {
	// Test: High volume write operations
	numWrites := 5000
	startTime := time.Now()
	
	for i := 0; i < numWrites; i++ {
		itemName := fmt.Sprintf("WriteTestItem%d", i)
		score := float64(i%10) + 0.1
		
		err := suite.repository.UpdateRecommendationScore(itemName, score)
		assert.NoError(suite.T(), err)
	}
	
	duration := time.Since(startTime)
	writesPerSecond := float64(numWrites) / duration.Seconds()

	// Verify data integrity
	topRated, err := suite.repository.GetTopRatedOrigamis(10)
	require.NoError(suite.T(), err)
	assert.Len(suite.T(), topRated, 10)

	// Performance assertions
	assert.Greater(suite.T(), writesPerSecond, 200.0, "Should handle > 200 writes/second")
	assert.Less(suite.T(), duration, 30*time.Second, "Should complete within 30 seconds")
}

func (suite *PerformanceTestSuite) TestConcurrentWriteOperations() {
	// Test: Concurrent write operations
	concurrentWriters := 20
	writesPerWriter := 100
	
	startTime := time.Now()
	
	var wg sync.WaitGroup
	errorChan := make(chan error, concurrentWriters*writesPerWriter)
	
	for writer := 0; writer < concurrentWriters; writer++ {
		wg.Add(1)
		go func(writerIndex int) {
			defer wg.Done()
			
			for write := 0; write < writesPerWriter; write++ {
				itemName := fmt.Sprintf("ConcurrentWrite_%d_%d", writerIndex, write)
				score := float64((writerIndex*writesPerWriter+write)%10) + 0.1
				
				err := suite.repository.UpdateRecommendationScore(itemName, score)
				if err != nil {
					errorChan <- err
				}
			}
		}(writer)
	}
	
	wg.Wait()
	close(errorChan)
	
	duration := time.Since(startTime)
	totalWrites := concurrentWriters * writesPerWriter
	writesPerSecond := float64(totalWrites) / duration.Seconds()

	// Check for errors
	errorCount := 0
	for err := range errorChan {
		if err != nil {
			errorCount++
		}
	}

	// Performance assertions
	assert.Equal(suite.T(), 0, errorCount, "Should have no errors during concurrent writes")
	assert.Greater(suite.T(), writesPerSecond, 100.0, "Should handle > 100 concurrent writes/second")
	assert.Less(suite.T(), duration, 25*time.Second, "Should complete within 25 seconds")
}

func (suite *PerformanceTestSuite) TestMixedWorkloadPerformance() {
	// Setup: Create initial dataset
	for i := 0; i < 200; i++ {
		err := suite.repository.UpdateRecommendationScore(fmt.Sprintf("MixedItem%d", i), float64(i%10))
		require.NoError(suite.T(), err)
	}

	// Test: Mixed read/write workload
	concurrentUsers := 30
	operationsPerUser := 50
	
	startTime := time.Now()
	
	var wg sync.WaitGroup
	var readOps, writeOps int64
	var mu sync.Mutex
	
	for user := 0; user < concurrentUsers; user++ {
		wg.Add(1)
		go func(userIndex int) {
			defer wg.Done()
			userID := fmt.Sprintf("mixed_user_%d", userIndex)
			
			for op := 0; op < operationsPerUser; op++ {
				if op%3 == 0 { // 33% writes
					itemName := fmt.Sprintf("MixedNewItem_%d_%d", userIndex, op)
					score := float64(op%10) + 0.1
					
					err := suite.repository.UpdateRecommendationScore(itemName, score)
					assert.NoError(suite.T(), err)
					
					mu.Lock()
					writeOps++
					mu.Unlock()
				} else { // 67% reads
					_, err := suite.repository.GetRecommendations(userID, 5)
					assert.NoError(suite.T(), err)
					
					mu.Lock()
					readOps++
					mu.Unlock()
				}
			}
		}(user)
	}
	
	wg.Wait()
	
	duration := time.Since(startTime)
	totalOperations := readOps + writeOps
	operationsPerSecond := float64(totalOperations) / duration.Seconds()

	// Performance assertions
	assert.Greater(suite.T(), operationsPerSecond, 300.0, "Should handle > 300 mixed ops/second")
	assert.Less(suite.T(), duration, 30*time.Second, "Should complete within 30 seconds")
	assert.Greater(suite.T(), readOps, writeOps, "Should have more reads than writes")
}

func (suite *PerformanceTestSuite) TestCacheHitRatePerformance() {
	// Setup: Create users and cache their recommendations
	numUsers := 100
	for i := 0; i < numUsers; i++ {
		userID := fmt.Sprintf("cache_user_%d", i)
		_, err := suite.repository.GetRecommendations(userID, 5)
		require.NoError(suite.T(), err)
	}

	// Test: Measure cache hit performance
	startTime := time.Now()
	
	// Perform operations that should hit cache
	for round := 0; round < 10; round++ {
		for i := 0; i < numUsers; i++ {
			userID := fmt.Sprintf("cache_user_%d", i)
			_, err := suite.repository.GetRecommendations(userID, 5)
			assert.NoError(suite.T(), err)
		}
	}
	
	duration := time.Since(startTime)
	totalCacheHits := numUsers * 10
	cacheHitsPerSecond := float64(totalCacheHits) / duration.Seconds()

	// Performance assertions for cache hits
	assert.Greater(suite.T(), cacheHitsPerSecond, 2000.0, "Cache hits should be > 2000/second")
	assert.Less(suite.T(), duration, 5*time.Second, "Cache operations should complete within 5 seconds")
}

func (suite *PerformanceTestSuite) TestBatchOperationPerformance() {
	// Test: Batch score updates
	batchSize := 1000
	scores := make(map[string]float64)
	
	for i := 0; i < batchSize; i++ {
		scores[fmt.Sprintf("BatchItem%d", i)] = float64(i%10) + 0.1
	}
	
	startTime := time.Now()
	err := suite.repository.BatchUpdateScores(scores)
	duration := time.Since(startTime)
	
	require.NoError(suite.T(), err)
	
	// Verify batch operation results
	topRated, err := suite.repository.GetTopRatedOrigamis(10)
	require.NoError(suite.T(), err)
	assert.Len(suite.T(), topRated, 10)
	
	// Performance assertions
	itemsPerSecond := float64(batchSize) / duration.Seconds()
	assert.Greater(suite.T(), itemsPerSecond, 500.0, "Batch operations should handle > 500 items/second")
	assert.Less(suite.T(), duration, 5*time.Second, "Batch operation should complete within 5 seconds")
}

func (suite *PerformanceTestSuite) TestConnectionPoolPerformance() {
	// Test: Stress connection pool
	concurrentConnections := 200
	operationsPerConnection := 20
	
	startTime := time.Now()
	
	var wg sync.WaitGroup
	errorChan := make(chan error, concurrentConnections*operationsPerConnection)
	
	for conn := 0; conn < concurrentConnections; conn++ {
		wg.Add(1)
		go func(connIndex int) {
			defer wg.Done()
			
			for op := 0; op < operationsPerConnection; op++ {
				// Simple operations to stress connection pool
				_, err := suite.client.Ping(suite.ctx).Result()
				if err != nil {
					errorChan <- err
				}
				
				// Small delay to simulate processing
				time.Sleep(1 * time.Millisecond)
			}
		}(conn)
	}
	
	wg.Wait()
	close(errorChan)
	
	duration := time.Since(startTime)
	totalOperations := concurrentConnections * operationsPerConnection
	operationsPerSecond := float64(totalOperations) / duration.Seconds()

	// Check for connection errors
	errorCount := 0
	for err := range errorChan {
		if err != nil {
			errorCount++
		}
	}

	// Performance assertions
	assert.Equal(suite.T(), 0, errorCount, "Should have no connection errors")
	assert.Greater(suite.T(), operationsPerSecond, 1000.0, "Connection pool should handle > 1000 ops/second")
	assert.Less(suite.T(), duration, 10*time.Second, "Should complete within 10 seconds")
}

func (suite *PerformanceTestSuite) TestMemoryUsageUnderLoad() {
	// Test: Monitor memory usage during sustained operations
	initialMemStats := &runtime.MemStats{}
	runtime.ReadMemStats(initialMemStats)
	
	// Sustained operations
	for batch := 0; batch < 50; batch++ {
		// Create and cache data
		for i := 0; i < 100; i++ {
			userID := fmt.Sprintf("memory_user_%d_%d", batch, i)
			_, err := suite.repository.GetRecommendations(userID, 5)
			assert.NoError(suite.T(), err)
		}
		
		// Update scores
		for i := 0; i < 50; i++ {
			itemName := fmt.Sprintf("MemoryItem_%d_%d", batch, i)
			err := suite.repository.UpdateRecommendationScore(itemName, float64(i%10))
			assert.NoError(suite.T(), err)
		}
		
		// Invalidate some cache entries
		if batch%10 == 0 {
			err := suite.repository.InvalidateAllRecommendations()
			assert.NoError(suite.T(), err)
		}
		
		// Force garbage collection periodically
		if batch%20 == 0 {
			runtime.GC()
		}
	}
	
	finalMemStats := &runtime.MemStats{}
	runtime.ReadMemStats(finalMemStats)
	
	memoryIncrease := finalMemStats.Alloc - initialMemStats.Alloc
	
	// Memory usage should not increase dramatically
	assert.Less(suite.T(), memoryIncrease, uint64(50*1024*1024), "Memory increase should be < 50MB")
}

func (suite *PerformanceTestSuite) TestLatencyUnderLoad() {
	// Setup: Create baseline data
	for i := 0; i < 100; i++ {
		err := suite.repository.UpdateRecommendationScore(fmt.Sprintf("LatencyItem%d", i), float64(i%10))
		require.NoError(suite.T(), err)
	}

	// Test: Measure latency under increasing load
	loadLevels := []int{10, 50, 100, 200}
	
	for _, load := range loadLevels {
		var latencies []time.Duration
		var wg sync.WaitGroup
		latencyChan := make(chan time.Duration, load*10)
		
		for user := 0; user < load; user++ {
			wg.Add(1)
			go func(userIndex int) {
				defer wg.Done()
				userID := fmt.Sprintf("latency_user_%d", userIndex)
				
				for op := 0; op < 10; op++ {
					start := time.Now()
					_, err := suite.repository.GetRecommendations(userID, 5)
					latency := time.Since(start)
					
					assert.NoError(suite.T(), err)
					latencyChan <- latency
				}
			}(user)
		}
		
		wg.Wait()
		close(latencyChan)
		
		// Collect latencies
		for latency := range latencyChan {
			latencies = append(latencies, latency)
		}
		
		// Calculate percentiles
		if len(latencies) > 0 {
			// Sort latencies for percentile calculation
			sort.Slice(latencies, func(i, j int) bool {
				return latencies[i] < latencies[j]
			})
			
			p50 := latencies[len(latencies)*50/100]
			p95 := latencies[len(latencies)*95/100]
			p99 := latencies[len(latencies)*99/100]
			
			// Latency assertions (should not degrade significantly under load)
			assert.Less(suite.T(), p50, 50*time.Millisecond, "P50 latency should be < 50ms at load %d", load)
			assert.Less(suite.T(), p95, 200*time.Millisecond, "P95 latency should be < 200ms at load %d", load)
			assert.Less(suite.T(), p99, 500*time.Millisecond, "P99 latency should be < 500ms at load %d", load)
		}
	}
}

func (suite *PerformanceTestSuite) TestThroughputScaling() {
	// Test: Measure throughput scaling with different concurrency levels
	concurrencyLevels := []int{1, 5, 10, 20, 50}
	operationsPerLevel := 1000
	
	for _, concurrency := range concurrencyLevels {
		startTime := time.Now()
		
		var wg sync.WaitGroup
		operationsPerWorker := operationsPerLevel / concurrency
		
		for worker := 0; worker < concurrency; worker++ {
			wg.Add(1)
			go func(workerIndex int) {
				defer wg.Done()
				userID := fmt.Sprintf("scaling_user_%d", workerIndex)
				
				for op := 0; op < operationsPerWorker; op++ {
					_, err := suite.repository.GetRecommendations(userID, 5)
					assert.NoError(suite.T(), err)
				}
			}(worker)
		}
		
		wg.Wait()
		
		duration := time.Since(startTime)
		throughput := float64(operationsPerLevel) / duration.Seconds()
		
		// Throughput should generally increase with concurrency (up to a point)
		if concurrency == 1 {
			assert.Greater(suite.T(), throughput, 100.0, "Single-threaded throughput should be > 100 ops/sec")
		} else if concurrency <= 20 {
			// Expect scaling up to moderate concurrency levels
			assert.Greater(suite.T(), throughput, float64(concurrency)*50.0, 
				"Throughput should scale with concurrency level %d", concurrency)
		}
		
		suite.T().Logf("Concurrency %d: %.1f ops/sec", concurrency, throughput)
	}
}

// Helper function to sort durations (Go doesn't have a built-in sort for time.Duration)
func sortDurations(durations []time.Duration) {
	for i := 0; i < len(durations)-1; i++ {
		for j := i + 1; j < len(durations); j++ {
			if durations[i] > durations[j] {
				durations[i], durations[j] = durations[j], durations[i]
			}
		}
	}
}

// Run the performance test suite
func TestPerformanceTestSuite(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping performance tests in short mode")
	}
	
	suite.Run(t, new(PerformanceTestSuite))
}

// Benchmark tests for more detailed performance analysis
func BenchmarkGetRecommendations(b *testing.B) {
	miniRedis, err := miniredis.Run()
	if err != nil {
		b.Fatal(err)
	}
	defer miniRedis.Close()

	client := redis.NewClient(&redis.Options{
		Addr: miniRedis.Addr(),
	})
	defer client.Close()

	repo := repository.NewTestEnhancedRedisRepository(client)

	// Setup test data
	for i := 0; i < 100; i++ {
		err := repo.UpdateRecommendationScore(fmt.Sprintf("BenchItem%d", i), float64(i%10))
		if err != nil {
			b.Fatal(err)
		}
	}

	b.ResetTimer()
	b.RunParallel(func(pb *testing.PB) {
		userCounter := 0
		for pb.Next() {
			userID := fmt.Sprintf("bench_user_%d", userCounter%100)
			_, err := repo.GetRecommendations(userID, 5)
			if err != nil {
				b.Fatal(err)
			}
			userCounter++
		}
	})
}

func BenchmarkUpdateRecommendationScore(b *testing.B) {
	miniRedis, err := miniredis.Run()
	if err != nil {
		b.Fatal(err)
	}
	defer miniRedis.Close()

	client := redis.NewClient(&redis.Options{
		Addr: miniRedis.Addr(),
	})
	defer client.Close()

	repo := repository.NewTestEnhancedRedisRepository(client)

	b.ResetTimer()
	b.RunParallel(func(pb *testing.PB) {
		itemCounter := 0
		for pb.Next() {
			itemName := fmt.Sprintf("BenchUpdateItem%d", itemCounter)
			score := float64(itemCounter%10) + 0.1
			err := repo.UpdateRecommendationScore(itemName, score)
			if err != nil {
				b.Fatal(err)
			}
			itemCounter++
		}
	})
}