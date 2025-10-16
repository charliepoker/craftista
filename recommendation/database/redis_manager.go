package database

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strconv"
	"time"

	"github.com/redis/go-redis/v9"
)

// RedisConfig holds the configuration for Redis connection
type RedisConfig struct {
	Host               string
	Port               string
	Password           string
	Database           int
	MaxRetries         int
	MinRetryBackoff    time.Duration
	MaxRetryBackoff    time.Duration
	DialTimeout        time.Duration
	ReadTimeout        time.Duration
	WriteTimeout       time.Duration
	PoolSize           int
	MinIdleConns       int
	MaxConnAge         time.Duration
	PoolTimeout        time.Duration
	IdleTimeout        time.Duration
	IdleCheckFrequency time.Duration
}

// RedisManager manages Redis connections with connection pooling and health monitoring
type RedisManager struct {
	client *redis.Client
	config *RedisConfig
	ctx    context.Context
}

// HealthStatus represents the health status of Redis connection
type HealthStatus struct {
	Status       string                 `json:"status"`
	Database     DatabaseHealthInfo     `json:"database"`
	Timestamp    string                 `json:"timestamp"`
}

// DatabaseHealthInfo contains detailed database health information
type DatabaseHealthInfo struct {
	Connected      bool                   `json:"connected"`
	ResponseTimeMs float64                `json:"response_time_ms,omitempty"`
	PoolStats      map[string]interface{} `json:"pool_stats,omitempty"`
	Error          string                 `json:"error,omitempty"`
}

// RecommendationCache represents cached recommendation data
type RecommendationCache struct {
	Key       string    `json:"key"`
	Data      string    `json:"data"`
	ExpiresAt time.Time `json:"expires_at"`
	CreatedAt time.Time `json:"created_at"`
}

// OrigamiRecommendation represents a recommendation for an origami
type OrigamiRecommendation struct {
	ID          string  `json:"id"`
	Name        string  `json:"name"`
	Description string  `json:"description"`
	ImageURL    string  `json:"image_url"`
	Score       float64 `json:"score"`
	Reason      string  `json:"reason"`
}

// NewRedisManager creates a new Redis manager with environment-based configuration
func NewRedisManager() (*RedisManager, error) {
	config := loadRedisConfig()
	
	// Create Redis client with connection pooling
	rdb := redis.NewClient(&redis.Options{
		Addr:            fmt.Sprintf("%s:%s", config.Host, config.Port),
		Password:        config.Password,
		DB:              config.Database,
		MaxRetries:      config.MaxRetries,
		MinRetryBackoff: config.MinRetryBackoff,
		MaxRetryBackoff: config.MaxRetryBackoff,
		DialTimeout:     config.DialTimeout,
		ReadTimeout:     config.ReadTimeout,
		WriteTimeout:    config.WriteTimeout,
		PoolSize:        config.PoolSize,
		MinIdleConns:    config.MinIdleConns,
		PoolTimeout:     config.PoolTimeout,
	})

	manager := &RedisManager{
		client: rdb,
		config: config,
		ctx:    context.Background(),
	}

	// Test the connection
	if err := manager.ping(); err != nil {
		return nil, fmt.Errorf("failed to connect to Redis: %w", err)
	}

	log.Printf("Successfully connected to Redis at %s:%s", config.Host, config.Port)
	return manager, nil
}

// loadRedisConfig loads Redis configuration from environment variables
func loadRedisConfig() *RedisConfig {
	return &RedisConfig{
		Host:               getEnv("REDIS_HOST", "localhost"),
		Port:               getEnv("REDIS_PORT", "6379"),
		Password:           getEnv("REDIS_PASSWORD", ""),
		Database:           getEnvAsInt("REDIS_DATABASE", 0),
		MaxRetries:         getEnvAsInt("REDIS_MAX_RETRIES", 3),
		MinRetryBackoff:    getEnvAsDuration("REDIS_MIN_RETRY_BACKOFF", "8ms"),
		MaxRetryBackoff:    getEnvAsDuration("REDIS_MAX_RETRY_BACKOFF", "512ms"),
		DialTimeout:        getEnvAsDuration("REDIS_DIAL_TIMEOUT", "5s"),
		ReadTimeout:        getEnvAsDuration("REDIS_READ_TIMEOUT", "3s"),
		WriteTimeout:       getEnvAsDuration("REDIS_WRITE_TIMEOUT", "3s"),
		PoolSize:           getEnvAsInt("REDIS_POOL_SIZE", 10),
		MinIdleConns:       getEnvAsInt("REDIS_MIN_IDLE_CONNS", 2),
		MaxConnAge:         getEnvAsDuration("REDIS_MAX_CONN_AGE", "30m"),
		PoolTimeout:        getEnvAsDuration("REDIS_POOL_TIMEOUT", "4s"),
		IdleTimeout:        getEnvAsDuration("REDIS_IDLE_TIMEOUT", "5m"),
		IdleCheckFrequency: getEnvAsDuration("REDIS_IDLE_CHECK_FREQUENCY", "1m"),
	}
}

// ping tests the Redis connection
func (rm *RedisManager) ping() error {
	ctx, cancel := context.WithTimeout(rm.ctx, 5*time.Second)
	defer cancel()
	
	return rm.client.Ping(ctx).Err()
}

// Close closes the Redis connection
func (rm *RedisManager) Close() error {
	if rm.client != nil {
		return rm.client.Close()
	}
	return nil
}

// GetClient returns the Redis client instance
func (rm *RedisManager) GetClient() *redis.Client {
	return rm.client
}

// HealthCheck performs a comprehensive health check on the Redis connection
func (rm *RedisManager) HealthCheck() HealthStatus {
	healthStatus := HealthStatus{
		Status: "unhealthy",
		Database: DatabaseHealthInfo{
			Connected: false,
		},
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	}

	// Test connection and measure response time
	start := time.Now()
	err := rm.ping()
	responseTime := time.Since(start).Seconds() * 1000 // Convert to milliseconds

	if err != nil {
		healthStatus.Database.Error = err.Error()
		log.Printf("Redis health check failed: %v", err)
		return healthStatus
	}

	// Get pool statistics
	poolStats := rm.getPoolStats()

	healthStatus.Status = "healthy"
	healthStatus.Database = DatabaseHealthInfo{
		Connected:      true,
		ResponseTimeMs: responseTime,
		PoolStats:      poolStats,
	}

	return healthStatus
}

// getPoolStats retrieves connection pool statistics
func (rm *RedisManager) getPoolStats() map[string]interface{} {
	stats := rm.client.PoolStats()
	
	return map[string]interface{}{
		"hits":         stats.Hits,
		"misses":       stats.Misses,
		"timeouts":     stats.Timeouts,
		"total_conns":  stats.TotalConns,
		"idle_conns":   stats.IdleConns,
		"stale_conns":  stats.StaleConns,
		"pool_size":    rm.config.PoolSize,
		"min_idle":     rm.config.MinIdleConns,
	}
}

// SetRecommendation caches a recommendation with TTL
func (rm *RedisManager) SetRecommendation(key string, recommendation interface{}, ttl time.Duration) error {
	ctx, cancel := context.WithTimeout(rm.ctx, rm.config.WriteTimeout)
	defer cancel()

	data, err := json.Marshal(recommendation)
	if err != nil {
		return fmt.Errorf("failed to marshal recommendation: %w", err)
	}

	return rm.client.Set(ctx, key, data, ttl).Err()
}

// GetRecommendation retrieves a cached recommendation
func (rm *RedisManager) GetRecommendation(key string, result interface{}) error {
	ctx, cancel := context.WithTimeout(rm.ctx, rm.config.ReadTimeout)
	defer cancel()

	data, err := rm.client.Get(ctx, key).Result()
	if err != nil {
		return err
	}

	return json.Unmarshal([]byte(data), result)
}

// DeleteRecommendation removes a cached recommendation
func (rm *RedisManager) DeleteRecommendation(key string) error {
	ctx, cancel := context.WithTimeout(rm.ctx, rm.config.WriteTimeout)
	defer cancel()

	return rm.client.Del(ctx, key).Err()
}

// SetOrigamiOfTheDay caches the origami of the day
func (rm *RedisManager) SetOrigamiOfTheDay(origami interface{}) error {
	key := fmt.Sprintf("origami:daily:%s", time.Now().Format("2006-01-02"))
	ttl := time.Until(time.Now().Add(24 * time.Hour).Truncate(24 * time.Hour))
	
	return rm.SetRecommendation(key, origami, ttl)
}

// GetOrigamiOfTheDay retrieves the cached origami of the day
func (rm *RedisManager) GetOrigamiOfTheDay(result interface{}) error {
	key := fmt.Sprintf("origami:daily:%s", time.Now().Format("2006-01-02"))
	return rm.GetRecommendation(key, result)
}

// InvalidateCache removes all cached recommendations matching a pattern
func (rm *RedisManager) InvalidateCache(pattern string) error {
	ctx, cancel := context.WithTimeout(rm.ctx, rm.config.WriteTimeout)
	defer cancel()

	keys, err := rm.client.Keys(ctx, pattern).Result()
	if err != nil {
		return err
	}

	if len(keys) > 0 {
		return rm.client.Del(ctx, keys...).Err()
	}

	return nil
}

// SetRecommendationScore sets a score for a recommendation (for ranking)
func (rm *RedisManager) SetRecommendationScore(key string, member string, score float64) error {
	ctx, cancel := context.WithTimeout(rm.ctx, rm.config.WriteTimeout)
	defer cancel()

	return rm.client.ZAdd(ctx, key, redis.Z{
		Score:  score,
		Member: member,
	}).Err()
}

// GetTopRecommendations retrieves top N recommendations by score
func (rm *RedisManager) GetTopRecommendations(key string, count int64) ([]string, error) {
	ctx, cancel := context.WithTimeout(rm.ctx, rm.config.ReadTimeout)
	defer cancel()

	return rm.client.ZRevRange(ctx, key, 0, count-1).Result()
}

// Utility functions for environment variable parsing
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvAsInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}

func getEnvAsDuration(key string, defaultValue string) time.Duration {
	if value := os.Getenv(key); value != "" {
		if duration, err := time.ParseDuration(value); err == nil {
			return duration
		}
	}
	if duration, err := time.ParseDuration(defaultValue); err == nil {
		return duration
	}
	return time.Second
}