package repository

import (
	"context"
	"recommendation/database"
	"time"

	"github.com/redis/go-redis/v9"
)

// NewTestEnhancedRedisRepository creates a repository for testing with a direct Redis client
func NewTestEnhancedRedisRepository(client *redis.Client) *EnhancedRedisRepository {
	// Initialize circuit breaker for Redis operations
	circuitBreaker := database.GetCircuitBreaker("test_redis_repository", nil)
	fallbackHandler := database.GetFallbackHandler()
	
	return &EnhancedRedisRepository{
		redisManager:         nil, // Not needed for testing
		client:              client,
		ctx:                 context.Background(),
		circuitBreaker:      circuitBreaker,
		fallbackHandler:     fallbackHandler,
		defaultTTL:          time.Hour,
		recommendationTTL:   time.Hour * 2,
		origamiOfDayTTL:     time.Hour * 24,
		userPreferencesTTL:  time.Hour * 24 * 7, // 1 week
	}
}