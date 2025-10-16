package tests

import (
	"context"
	"fmt"
	"recommendation/repository"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/stretchr/testify/suite"
)

// RedisOperationsTestSuite provides comprehensive testing for Redis operations
type RedisOperationsTestSuite struct {
	suite.Suite
	miniRedis  *miniredis.Miniredis
	client     *redis.Client
	repository *repository.EnhancedRedisRepository
	ctx        context.Context
}

func (suite *RedisOperationsTestSuite) SetupSuite() {
	// Start mini Redis server for testing
	var err error
	suite.miniRedis, err = miniredis.Run()
	require.NoError(suite.T(), err)

	// Create Redis client
	suite.client = redis.NewClient(&redis.Options{
		Addr: suite.miniRedis.Addr(),
	})

	suite.ctx = context.Background()
}

func (suite *RedisOperationsTestSuite) SetupTest() {
	// Clear Redis data before each test
	suite.miniRedis.FlushAll()

	// Create repository using test constructor
	suite.repository = repository.NewTestEnhancedRedisRepository(suite.client)
}

func (suite *RedisOperationsTestSuite) TearDownSuite() {
	if suite.client != nil {
		suite.client.Close()
	}
	if suite.miniRedis != nil {
		suite.miniRedis.Close()
	}
}

// Test Redis caching functionality
func (suite *RedisOperationsTestSuite) TestRedisCaching_Success() {
	// Given
	userID := "test-user-123"
	limit := 5

	// When - First call should cache the result
	recommendations1, err := suite.repository.GetRecommendations(userID, limit)
	require.NoError(suite.T(), err)

	// When - Second call should return cached result
	recommendations2, err := suite.repository.GetRecommendations(userID, limit)

	// Then
	assert.NoError(suite.T(), err)
	assert.Equal(suite.T(), len(recommendations1), len(recommendations2))
	
	// Verify cache was used by checking Redis directly
	cacheKey := fmt.Sprintf("recommendations:user:%s:limit:%d", userID, limit)
	exists, err := suite.client.Exists(suite.ctx, cacheKey).Result()
	assert.NoError(suite.T(), err)
	assert.Equal(suite.T(), int64(1), exists)
}

func (suite *RedisOperationsTestSuite) TestRedisCaching_TTLExpiration() {
	// Given
	userID := "ttl-test-user"
	
	// When - Get recommendations to cache them
	_, err := suite.repository.GetRecommendations(userID, 3)
	require.NoError(suite.T(), err)

	// Verify cache exists
	cacheKey := fmt.Sprintf("recommendations:user:%s:limit:%d", userID, 3)
	exists, err := suite.client.Exists(suite.ctx, cacheKey).Result()
	require.NoError(suite.T(), err)
	assert.Equal(suite.T(), int64(1), exists)

	// Fast-forward time in mini Redis to simulate TTL expiration
	suite.miniRedis.FastForward(3 * time.Hour) // Exceed recommendation TTL

	// Then - Cache should be expired
	exists, err = suite.client.Exists(suite.ctx, cacheKey).Result()
	assert.NoError(suite.T(), err)
	assert.Equal(suite.T(), int64(0), exists)
}

func (suite *RedisOperationsTestSuite) TestCacheInvalidation_UserSpecific() {
	// Given - Cache recommendations for multiple users
	userIDs := []string{"user1", "user2", "user3"}
	for _, userID := range userIDs {
		_, err := suite.repository.GetRecommendations(userID, 3)
		require.NoError(suite.T(), err)
	}

	// Verify all caches exist
	for _, userID := range userIDs {
		keys, err := suite.client.Keys(suite.ctx, fmt.Sprintf("recommendations:user:%s:*", userID)).Result()
		require.NoError(suite.T(), err)
		assert.NotEmpty(suite.T(), keys)
	}

	// When - Invalidate cache for one user
	err := suite.repository.InvalidateUserRecommendations("user2")
	require.NoError(suite.T(), err)

	// Then - Only user2's cache should be cleared
	keys, err := suite.client.Keys(suite.ctx, "recommendations:user:user2:*").Result()
	assert.NoError(suite.T(), err)
	assert.Empty(suite.T(), keys)

	// Other users' caches should still exist
	for _, userID := range []string{"user1", "user3"} {
		keys, err := suite.client.Keys(suite.ctx, fmt.Sprintf("recommendations:user:%s:*", userID)).Result()
		assert.NoError(suite.T(), err)
		assert.NotEmpty(suite.T(), keys)
	}
}

func (suite *RedisOperationsTestSuite) TestCacheInvalidation_AllRecommendations() {
	// Given - Cache various types of data
	_, err := suite.repository.GetRecommendations("user1", 3)
	require.NoError(suite.T(), err)
	_, err = suite.repository.GetOrigamiOfTheDay()
	require.NoError(suite.T(), err)
	_, err = suite.repository.GetTopRatedOrigamis(5)
	require.NoError(suite.T(), err)

	// Verify caches exist
	allKeys, err := suite.client.Keys(suite.ctx, "*").Result()
	require.NoError(suite.T(), err)
	assert.NotEmpty(suite.T(), allKeys)

	// When - Invalidate all recommendations
	err = suite.repository.InvalidateAllRecommendations()
	require.NoError(suite.T(), err)

	// Then - All recommendation caches should be cleared
	patterns := []string{"recommendations:*", "top_rated:*", "origami:daily:*"}
	for _, pattern := range patterns {
		keys, err := suite.client.Keys(suite.ctx, pattern).Result()
		assert.NoError(suite.T(), err)
		assert.Empty(suite.T(), keys)
	}
}

func (suite *RedisOperationsTestSuite) TestOrigamiOfTheDay_Caching() {
	// When - First call should generate and cache
	origami1, err := suite.repository.GetOrigamiOfTheDay()
	require.NoError(suite.T(), err)

	// When - Second call should return cached result
	origami2, err := suite.repository.GetOrigamiOfTheDay()
	require.NoError(suite.T(), err)

	// Then - Should return same origami (cached)
	assert.Equal(suite.T(), origami1.Name, origami2.Name)
	assert.Equal(suite.T(), origami1.Description, origami2.Description)

	// Verify cache exists with correct TTL
	cacheKey := fmt.Sprintf("origami:daily:%s", time.Now().Format("2006-01-02"))
	exists, err := suite.client.Exists(suite.ctx, cacheKey).Result()
	assert.NoError(suite.T(), err)
	assert.Equal(suite.T(), int64(1), exists)

	// Check TTL is set (should be until end of day)
	ttl, err := suite.client.TTL(suite.ctx, cacheKey).Result()
	assert.NoError(suite.T(), err)
	assert.Greater(suite.T(), ttl, time.Duration(0))
}

func (suite *RedisOperationsTestSuite) TestScoreOperations_UpdateAndRetrieve() {
	// Given
	scores := map[string]float64{
		"Crane":     9.5,
		"Butterfly": 8.7,
		"Dragon":    9.8,
		"Flower":    7.2,
		"Elephant":  8.1,
	}

	// When - Update scores
	for name, score := range scores {
		err := suite.repository.UpdateRecommendationScore(name, score)
		require.NoError(suite.T(), err)
	}

	// Then - Verify scores were stored correctly
	for name, expectedScore := range scores {
		actualScore, err := suite.client.ZScore(suite.ctx, "origami:scores", name).Result()
		assert.NoError(suite.T(), err)
		assert.Equal(suite.T(), expectedScore, actualScore)
	}

	// Test top rated retrieval
	topRated, err := suite.repository.GetTopRatedOrigamis(3)
	require.NoError(suite.T(), err)
	assert.Len(suite.T(), topRated, 3)
	
	// Verify order (highest to lowest)
	assert.Equal(suite.T(), "Dragon", topRated[0])    // 9.8
	assert.Equal(suite.T(), "Crane", topRated[1])     // 9.5
	assert.Equal(suite.T(), "Butterfly", topRated[2]) // 8.7
}

func (suite *RedisOperationsTestSuite) TestScoreOperations_BatchUpdate() {
	// Given
	scores := map[string]float64{
		"Batch1": 8.5,
		"Batch2": 7.2,
		"Batch3": 9.1,
		"Batch4": 6.8,
	}

	// When - Batch update scores
	err := suite.repository.BatchUpdateScores(scores)
	require.NoError(suite.T(), err)

	// Then - Verify all scores were updated
	for name, expectedScore := range scores {
		actualScore, err := suite.client.ZScore(suite.ctx, "origami:scores", name).Result()
		assert.NoError(suite.T(), err)
		assert.Equal(suite.T(), expectedScore, actualScore)
	}

	// Verify score history was recorded
	for name := range scores {
		historyKey := fmt.Sprintf("origami:score_history:%s", name)
		historyLength, err := suite.client.LLen(suite.ctx, historyKey).Result()
		assert.NoError(suite.T(), err)
		assert.Equal(suite.T(), int64(1), historyLength)
	}
}

func (suite *RedisOperationsTestSuite) TestPersonalizedRecommendations_Caching() {
	// Given
	userID := "personalized-user"
	preferences := repository.UserPreferences{
		FavoriteCategories: []string{"animals", "birds"},
		PreferredColors:    []string{"blue", "green"},
		DifficultyLevel:    "intermediate",
	}

	// When - First call should generate and cache
	recommendations1, err := suite.repository.GetPersonalizedRecommendations(userID, preferences, 5)
	require.NoError(suite.T(), err)

	// When - Second call with same preferences should return cached result
	recommendations2, err := suite.repository.GetPersonalizedRecommendations(userID, preferences, 5)
	require.NoError(suite.T(), err)

	// Then - Should return same recommendations (cached)
	assert.Equal(suite.T(), len(recommendations1), len(recommendations2))
	for i, rec1 := range recommendations1 {
		assert.Equal(suite.T(), rec1.Name, recommendations2[i].Name)
	}

	// Verify user preferences were stored
	prefsKey := fmt.Sprintf("user:preferences:%s", userID)
	exists, err := suite.client.Exists(suite.ctx, prefsKey).Result()
	assert.NoError(suite.T(), err)
	assert.Equal(suite.T(), int64(1), exists)
}

func (suite *RedisOperationsTestSuite) TestCacheWarmup_Success() {
	// When - Warm cache
	err := suite.repository.WarmCache()
	require.NoError(suite.T(), err)

	// Then - Verify cache entries were created
	allKeys, err := suite.client.Keys(suite.ctx, "*").Result()
	assert.NoError(suite.T(), err)
	assert.NotEmpty(suite.T(), allKeys)

	// Verify specific cache entries exist
	dailyKey := fmt.Sprintf("origami:daily:%s", time.Now().Format("2006-01-02"))
	exists, err := suite.client.Exists(suite.ctx, dailyKey).Result()
	assert.NoError(suite.T(), err)
	assert.Equal(suite.T(), int64(1), exists)

	// Verify user recommendations were cached
	userKeys, err := suite.client.Keys(suite.ctx, "recommendations:user:*").Result()
	assert.NoError(suite.T(), err)
	assert.NotEmpty(suite.T(), userKeys)
}

func (suite *RedisOperationsTestSuite) TestUserCacheWarmup_Success() {
	// Given
	userID := "warmup-test-user"

	// When - Warm user-specific cache
	err := suite.repository.WarmUserCache(userID)
	require.NoError(suite.T(), err)

	// Then - Verify user-specific cache entries were created
	userKeys, err := suite.client.Keys(suite.ctx, fmt.Sprintf("recommendations:user:%s:*", userID)).Result()
	assert.NoError(suite.T(), err)
	assert.NotEmpty(suite.T(), userKeys)

	// Verify user activity was recorded
	activityKey := fmt.Sprintf("user:activity:%s", userID)
	exists, err := suite.client.Exists(suite.ctx, activityKey).Result()
	assert.NoError(suite.T(), err)
	assert.Equal(suite.T(), int64(1), exists)
}

func (suite *RedisOperationsTestSuite) TestCacheStats_Accuracy() {
	// Given - Generate some cache activity
	_, err := suite.repository.GetRecommendations("stats-user", 3)
	require.NoError(suite.T(), err)
	
	// Generate cache hit
	_, err = suite.repository.GetRecommendations("stats-user", 3)
	require.NoError(suite.T(), err)

	// When - Get cache stats
	stats, err := suite.repository.GetCacheStats()
	require.NoError(suite.T(), err)

	// Then - Verify stats structure
	assert.NotNil(suite.T(), stats)
	assert.Contains(suite.T(), stats, "cache_hits")
	assert.Contains(suite.T(), stats, "cache_misses")
	assert.Contains(suite.T(), stats, "hit_rate")
	assert.Contains(suite.T(), stats, "pool_stats")
	assert.Contains(suite.T(), stats, "timestamp")

	// Verify hit rate calculation
	hitRate, ok := stats["hit_rate"].(float64)
	assert.True(suite.T(), ok)
	assert.GreaterOrEqual(suite.T(), hitRate, 0.0)
	assert.LessOrEqual(suite.T(), hitRate, 100.0)
}

func (suite *RedisOperationsTestSuite) TestUserEngagementTracking() {
	// Given
	userID := "engagement-user"

	// When - Generate user activity
	_, err := suite.repository.GetRecommendations(userID, 3)
	require.NoError(suite.T(), err)
	_, err = suite.repository.GetRecommendations(userID, 5)
	require.NoError(suite.T(), err)

	// When - Get engagement stats
	stats, err := suite.repository.GetUserEngagementStats(userID)
	require.NoError(suite.T(), err)

	// Then - Verify engagement tracking
	assert.Equal(suite.T(), userID, stats.UserID)
	assert.GreaterOrEqual(suite.T(), stats.TotalRecommendations, int64(1))
	assert.False(suite.T(), stats.LastActivity.IsZero())

	// Verify activity data in Redis
	activityKey := fmt.Sprintf("user:activity:%s", userID)
	totalRecs, err := suite.client.HGet(suite.ctx, activityKey, "total_recommendations").Result()
	assert.NoError(suite.T(), err)
	assert.NotEmpty(suite.T(), totalRecs)
}

// Test error handling and fallback behavior
func (suite *RedisOperationsTestSuite) TestFallbackBehavior_RedisUnavailable() {
	// Given - Close Redis connection to simulate failure
	suite.client.Close()

	// When - Try to get recommendations (should trigger fallback)
	_, err := suite.repository.GetRecommendations("fallback-user", 5)
	
	// Then - Should handle gracefully (exact behavior depends on circuit breaker implementation)
	// The test verifies that the system doesn't crash and handles the error appropriately
	if err != nil {
		assert.Contains(suite.T(), err.Error(), "connection")
	}

	// Recreate client for cleanup
	suite.client = redis.NewClient(&redis.Options{
		Addr: suite.miniRedis.Addr(),
	})
}

func (suite *RedisOperationsTestSuite) TestConcurrentOperations_ThreadSafety() {
	// Given
	userID := "concurrent-user"
	numGoroutines := 10

	// When - Perform concurrent operations
	done := make(chan bool, numGoroutines)
	errors := make(chan error, numGoroutines)

	for i := 0; i < numGoroutines; i++ {
		go func(id int) {
			defer func() { done <- true }()
			
			// Perform various operations concurrently
			_, err := suite.repository.GetRecommendations(userID, 3)
			if err != nil {
				errors <- err
				return
			}
			
			err = suite.repository.UpdateRecommendationScore(fmt.Sprintf("Concurrent%d", id), float64(id%10))
			if err != nil {
				errors <- err
				return
			}
		}(i)
	}

	// Wait for all goroutines to complete
	for i := 0; i < numGoroutines; i++ {
		<-done
	}

	// Then - Check for errors
	close(errors)
	for err := range errors {
		assert.NoError(suite.T(), err)
	}

	// Verify data integrity
	topRated, err := suite.repository.GetTopRatedOrigamis(numGoroutines)
	assert.NoError(suite.T(), err)
	assert.LessOrEqual(suite.T(), len(topRated), numGoroutines)
}

func (suite *RedisOperationsTestSuite) TestDataConsistency_MultipleUpdates() {
	// Given
	origamiName := "Consistency Test"
	scores := []float64{5.0, 7.5, 9.0, 6.2, 8.8}

	// When - Update score multiple times
	for _, score := range scores {
		err := suite.repository.UpdateRecommendationScore(origamiName, score)
		require.NoError(suite.T(), err)
	}

	// Then - Verify final score is correct (should be last update)
	finalScore, err := suite.client.ZScore(suite.ctx, "origami:scores", origamiName).Result()
	assert.NoError(suite.T(), err)
	assert.Equal(suite.T(), scores[len(scores)-1], finalScore)

	// Verify score history was recorded
	historyKey := fmt.Sprintf("origami:score_history:%s", origamiName)
	historyLength, err := suite.client.LLen(suite.ctx, historyKey).Result()
	assert.NoError(suite.T(), err)
	assert.Equal(suite.T(), int64(len(scores)), historyLength)
}

func (suite *RedisOperationsTestSuite) TestHealthCheck_Success() {
	// When
	status := suite.repository.HealthCheck()

	// Then
	assert.Equal(suite.T(), "healthy", status.Status)
	assert.True(suite.T(), status.CacheConnected)
	assert.Greater(suite.T(), status.ResponseTime, time.Duration(0))
	assert.GreaterOrEqual(suite.T(), status.ErrorRate, 0.0)
	assert.NotNil(suite.T(), status.Details)
}

// Unit tests for validation functions
func TestValidationFunctions(t *testing.T) {
	miniRedis, err := miniredis.Run()
	require.NoError(t, err)
	defer miniRedis.Close()

	client := redis.NewClient(&redis.Options{
		Addr: miniRedis.Addr(),
	})
	defer client.Close()

	repo := repository.NewTestEnhancedRedisRepository(client)

	t.Run("ValidateUserID", func(t *testing.T) {
		// Test invalid user IDs
		invalidUserIDs := []string{"", "   ", "\t\n"}
		for _, userID := range invalidUserIDs {
			_, err := repo.GetRecommendations(userID, 5)
			assert.Error(t, err)
			assert.Contains(t, err.Error(), "User ID cannot be empty")
		}

		// Test valid user ID
		_, err := repo.GetRecommendations("valid-user", 5)
		assert.NoError(t, err)
	})

	t.Run("ValidateScore", func(t *testing.T) {
		// Test invalid scores
		invalidScores := []float64{-1.0, 11.0, -5.5, 15.0}
		for _, score := range invalidScores {
			err := repo.UpdateRecommendationScore("Test", score)
			assert.Error(t, err)
			assert.Contains(t, err.Error(), "Score must be between 0 and 10")
		}

		// Test valid scores
		validScores := []float64{0.0, 5.5, 10.0, 7.25}
		for _, score := range validScores {
			err := repo.UpdateRecommendationScore("Test", score)
			assert.NoError(t, err)
		}
	})
}

// Test cache TTL functionality
func TestCacheTTLFunctionality(t *testing.T) {
	miniRedis, err := miniredis.Run()
	require.NoError(t, err)
	defer miniRedis.Close()

	client := redis.NewClient(&redis.Options{
		Addr: miniRedis.Addr(),
	})
	defer client.Close()

	repo := repository.NewTestEnhancedRedisRepository(client)

	t.Run("RecommendationTTL", func(t *testing.T) {
		userID := "ttl-user"
		
		// Get recommendations to cache them
		_, err := repo.GetRecommendations(userID, 3)
		require.NoError(t, err)

		// Check TTL is set
		cacheKey := fmt.Sprintf("recommendations:user:%s:limit:%d", userID, 3)
		ttl, err := client.TTL(context.Background(), cacheKey).Result()
		assert.NoError(t, err)
		assert.Greater(t, ttl, time.Duration(0))
		assert.LessOrEqual(t, ttl, 2*time.Hour) // Should be within recommendation TTL
	})

	t.Run("OrigamiOfTheDayTTL", func(t *testing.T) {
		// Get origami of the day to cache it
		_, err := repo.GetOrigamiOfTheDay()
		require.NoError(t, err)

		// Check TTL is set until end of day
		cacheKey := fmt.Sprintf("origami:daily:%s", time.Now().Format("2006-01-02"))
		ttl, err := client.TTL(context.Background(), cacheKey).Result()
		assert.NoError(t, err)
		assert.Greater(t, ttl, time.Duration(0))
		assert.LessOrEqual(t, ttl, 24*time.Hour)
	})
}

// Test batch operations
func TestBatchOperations(t *testing.T) {
	miniRedis, err := miniredis.Run()
	require.NoError(t, err)
	defer miniRedis.Close()

	client := redis.NewClient(&redis.Options{
		Addr: miniRedis.Addr(),
	})
	defer client.Close()

	repo := repository.NewTestEnhancedRedisRepository(client)

	t.Run("BatchUpdateScores", func(t *testing.T) {
		scores := map[string]float64{
			"Batch1": 8.5,
			"Batch2": 7.2,
			"Batch3": 9.1,
		}

		err := repo.BatchUpdateScores(scores)
		assert.NoError(t, err)

		// Verify all scores were updated
		for name, expectedScore := range scores {
			actualScore, err := client.ZScore(context.Background(), "origami:scores", name).Result()
			assert.NoError(t, err)
			assert.Equal(t, expectedScore, actualScore)
		}
	})

	t.Run("BatchInvalidateUsers", func(t *testing.T) {
		userIDs := []string{"batch1", "batch2", "batch3"}
		
		// Cache data for users
		for _, userID := range userIDs {
			_, err := repo.GetRecommendations(userID, 3)
			require.NoError(t, err)
		}

		// Batch invalidate
		err := repo.BatchInvalidateUsers(userIDs)
		assert.NoError(t, err)

		// Verify all caches were cleared
		for _, userID := range userIDs {
			keys, err := client.Keys(context.Background(), fmt.Sprintf("recommendations:user:%s:*", userID)).Result()
			assert.NoError(t, err)
			assert.Empty(t, keys)
		}
	})
}

// Run the test suite
func TestRedisOperationsTestSuite(t *testing.T) {
	suite.Run(t, new(RedisOperationsTestSuite))
}