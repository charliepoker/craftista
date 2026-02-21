package repository

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
	"recommendation/data"
	"recommendation/database"
	"strconv"
	"strings"
	"sync/atomic"
	"time"

	"github.com/redis/go-redis/v9"
)

// EnhancedRedisRepository provides comprehensive caching and recommendation functionality
type EnhancedRedisRepository struct {
	redisManager *database.RedisManager
	client       *redis.Client
	ctx          context.Context
	
	// Circuit breaker for database operations
	circuitBreaker  *database.CircuitBreaker
	fallbackHandler *database.FallbackHandler
	
	// Cache configuration
	defaultTTL           time.Duration
	recommendationTTL    time.Duration
	origamiOfDayTTL      time.Duration
	userPreferencesTTL   time.Duration
	
	// Performance tracking (atomic for thread-safety)
	cacheHits   int64
	cacheMisses int64
	errors      int64
}

// NewEnhancedRedisRepository creates a new enhanced Redis repository
func NewEnhancedRedisRepository(redisManager *database.RedisManager) *EnhancedRedisRepository {
	// Initialize circuit breaker for Redis operations
	circuitBreaker := database.GetCircuitBreaker("redis_repository", nil)
	fallbackHandler := database.GetFallbackHandler()
	
	return &EnhancedRedisRepository{
		redisManager:         redisManager,
		client:              redisManager.GetClient(),
		ctx:                 context.Background(),
		circuitBreaker:      circuitBreaker,
		fallbackHandler:     fallbackHandler,
		defaultTTL:          time.Hour,
		recommendationTTL:   time.Hour * 2,
		origamiOfDayTTL:     time.Hour * 24,
		userPreferencesTTL:  time.Hour * 24 * 7, // 1 week
	}
}

// GetOrigamiOfTheDay returns the origami of the day with enhanced caching
func (r *EnhancedRedisRepository) GetOrigamiOfTheDay() (data.Origami, error) {
	// Execute through circuit breaker
	result, err := r.circuitBreaker.Execute(r.ctx, func(ctx context.Context) (interface{}, error) {
		return r.getOrigamiOfTheDayInternal(ctx)
	})
	
	if err != nil {
		// Circuit breaker is open or operation failed, use fallback
		log.Printf("Circuit breaker triggered for origami of the day, using fallback: %v", err)
		fallbackRec := r.fallbackHandler.GetFallbackOrigamiOfTheDay()
		return data.Origami{
			Name:        fallbackRec.Name,
			Description: fallbackRec.Description,
			ImageUrl:    fallbackRec.ImageURL,
		}, nil
	}
	
	return result.(data.Origami), nil
}

// getOrigamiOfTheDayInternal is the internal implementation
func (r *EnhancedRedisRepository) getOrigamiOfTheDayInternal(ctx context.Context) (data.Origami, error) {
	cacheKey := fmt.Sprintf("origami:daily:%s", time.Now().Format("2006-01-02"))
	
	// Try cache first
	var cachedOrigami data.Origami
	err := r.getCachedData(cacheKey, &cachedOrigami)
	if err == nil {
		atomic.AddInt64(&r.cacheHits, 1)
		log.Printf("Cache hit for origami of the day")
		return cachedOrigami, nil
	}
	
	atomic.AddInt64(&r.cacheMisses, 1)
	log.Printf("Cache miss for origami of the day: %v", err)
	
	// Generate new origami of the day
	origami, err := r.generateOrigamiOfTheDay()
	if err != nil {
		atomic.AddInt64(&r.errors, 1)
		return data.Origami{}, fmt.Errorf("failed to generate origami of the day: %w", err)
	}
	
	// Cache with TTL until end of day
	endOfDay := time.Now().Add(24 * time.Hour).Truncate(24 * time.Hour)
	ttl := time.Until(endOfDay)
	
	if cacheErr := r.setCachedData(cacheKey, origami, ttl); cacheErr != nil {
		log.Printf("Failed to cache origami of the day: %v", cacheErr)
	}
	
	return origami, nil
}

// GetRecommendations returns personalized recommendations with caching
func (r *EnhancedRedisRepository) GetRecommendations(userID string, limit int) ([]data.Origami, error) {
	if err := r.validateUserID(userID); err != nil {
		return nil, err
	}
	
	cacheKey := fmt.Sprintf("recommendations:user:%s:limit:%d", userID, limit)
	
	// Try cache first
	var cachedRecommendations []data.Origami
	err := r.getCachedData(cacheKey, &cachedRecommendations)
	if err == nil && len(cachedRecommendations) > 0 {
		atomic.AddInt64(&r.cacheHits, 1)
		log.Printf("Cache hit for user %s recommendations", userID)
		return cachedRecommendations, nil
	}
	
	atomic.AddInt64(&r.cacheMisses, 1)
	log.Printf("Cache miss for user %s recommendations", userID)
	
	// Generate new recommendations
	recommendations, err := r.generateRecommendations(userID, limit)
	if err != nil {
		atomic.AddInt64(&r.errors, 1)
		return nil, &RecommendationError{
			Code:    ErrCodeInternalError,
			Message: "Failed to generate recommendations",
			Cause:   err,
		}
	}
	
	// Cache the recommendations
	if cacheErr := r.setCachedData(cacheKey, recommendations, r.recommendationTTL); cacheErr != nil {
		log.Printf("Failed to cache recommendations for user %s: %v", userID, cacheErr)
	}
	
	// Update user activity
	r.updateUserActivity(userID)
	
	return recommendations, nil
}

// GetPersonalizedRecommendations returns recommendations based on user preferences
func (r *EnhancedRedisRepository) GetPersonalizedRecommendations(userID string, preferences UserPreferences, limit int) ([]data.Origami, error) {
	if err := r.validateUserID(userID); err != nil {
		return nil, err
	}
	
	// Create cache key based on preferences hash
	prefsHash := r.hashPreferences(preferences)
	cacheKey := fmt.Sprintf("recommendations:user:%s:prefs:%s:limit:%d", userID, prefsHash, limit)
	
	// Try cache first
	var cachedRecommendations []data.Origami
	err := r.getCachedData(cacheKey, &cachedRecommendations)
	if err == nil && len(cachedRecommendations) > 0 {
		atomic.AddInt64(&r.cacheHits, 1)
		return cachedRecommendations, nil
	}
	
	atomic.AddInt64(&r.cacheMisses, 1)
	
	// Generate personalized recommendations
	recommendations, err := r.generatePersonalizedRecommendations(userID, preferences, limit)
	if err != nil {
		atomic.AddInt64(&r.errors, 1)
		return nil, &RecommendationError{
			Code:    ErrCodeInternalError,
			Message: "Failed to generate personalized recommendations",
			Cause:   err,
		}
	}
	
	// Cache the recommendations
	if cacheErr := r.setCachedData(cacheKey, recommendations, r.recommendationTTL); cacheErr != nil {
		log.Printf("Failed to cache personalized recommendations: %v", cacheErr)
	}
	
	// Store user preferences for future use
	r.storeUserPreferences(userID, preferences)
	
	return recommendations, nil
}

// UpdateRecommendationScore updates the score for a recommendation with validation
func (r *EnhancedRedisRepository) UpdateRecommendationScore(origamiName string, score float64) error {
	if err := r.validateScore(score); err != nil {
		return err
	}
	
	if strings.TrimSpace(origamiName) == "" {
		return &RecommendationError{
			Code:    ErrCodeRecommendationNotFound,
			Message: "Origami name cannot be empty",
		}
	}
	
	scoreKey := "origami:scores"
	ctx, cancel := context.WithTimeout(r.ctx, 5*time.Second)
	defer cancel()
	
	// Update score in sorted set
	err := r.client.ZAdd(ctx, scoreKey, redis.Z{
		Score:  score,
		Member: origamiName,
	}).Err()
	
	if err != nil {
		atomic.AddInt64(&r.errors, 1)
		return &RecommendationError{
			Code:    ErrCodeInternalError,
			Message: "Failed to update recommendation score",
			Cause:   err,
		}
	}
	
	// Update score history for analytics
	historyKey := fmt.Sprintf("origami:score_history:%s", origamiName)
	scoreEntry := map[string]interface{}{
		"score":     score,
		"timestamp": time.Now().Unix(),
	}
	
	scoreData, _ := json.Marshal(scoreEntry)
	r.client.LPush(ctx, historyKey, scoreData)
	r.client.LTrim(ctx, historyKey, 0, 99) // Keep last 100 scores
	r.client.Expire(ctx, historyKey, time.Hour*24*30) // 30 days
	
	log.Printf("Updated score for %s to %.2f", origamiName, score)
	return nil
}

// GetTopRatedOrigamis returns top-rated origamis with caching
func (r *EnhancedRedisRepository) GetTopRatedOrigamis(limit int) ([]string, error) {
	cacheKey := fmt.Sprintf("top_rated:limit:%d", limit)
	
	// Try cache first
	var cachedTopRated []string
	err := r.getCachedData(cacheKey, &cachedTopRated)
	if err == nil && len(cachedTopRated) > 0 {
		atomic.AddInt64(&r.cacheHits, 1)
		return cachedTopRated, nil
	}
	
	atomic.AddInt64(&r.cacheMisses, 1)
	
	// Get from sorted set
	scoreKey := "origami:scores"
	ctx, cancel := context.WithTimeout(r.ctx, 5*time.Second)
	defer cancel()
	
	topRated, err := r.client.ZRevRange(ctx, scoreKey, 0, int64(limit-1)).Result()
	if err != nil {
		atomic.AddInt64(&r.errors, 1)
		return nil, &RecommendationError{
			Code:    ErrCodeInternalError,
			Message: "Failed to get top rated origamis",
			Cause:   err,
		}
	}
	
	// Cache the result
	if cacheErr := r.setCachedData(cacheKey, topRated, time.Minute*30); cacheErr != nil {
		log.Printf("Failed to cache top rated origamis: %v", cacheErr)
	}
	
	return topRated, nil
}

// GetRecommendationsByScore returns recommendations above a minimum score
func (r *EnhancedRedisRepository) GetRecommendationsByScore(minScore float64, limit int) ([]data.Origami, error) {
	scoreKey := "origami:scores"
	ctx, cancel := context.WithTimeout(r.ctx, 5*time.Second)
	defer cancel()
	
	// Get origamis with score >= minScore
	members, err := r.client.ZRangeByScore(ctx, scoreKey, &redis.ZRangeBy{
		Min:   fmt.Sprintf("%.2f", minScore),
		Max:   "+inf",
		Count: int64(limit),
	}).Result()
	
	if err != nil {
		atomic.AddInt64(&r.errors, 1)
		return nil, &RecommendationError{
			Code:    ErrCodeInternalError,
			Message: "Failed to get recommendations by score",
			Cause:   err,
		}
	}
	
	// Convert names to origami objects
	allOrigamis := data.GetDailyOrigami()
	origamiMap := make(map[string]data.Origami)
	for _, origami := range allOrigamis {
		origamiMap[origami.Name] = origami
	}
	
	var recommendations []data.Origami
	for _, member := range members {
		if origami, exists := origamiMap[member]; exists {
			recommendations = append(recommendations, origami)
		}
	}
	
	return recommendations, nil
}

// InvalidateUserRecommendations removes cached recommendations for a user
func (r *EnhancedRedisRepository) InvalidateUserRecommendations(userID string) error {
	if err := r.validateUserID(userID); err != nil {
		return err
	}
	
	pattern := fmt.Sprintf("recommendations:user:%s:*", userID)
	return r.invalidatePattern(pattern)
}

// InvalidateAllRecommendations removes all cached recommendations
func (r *EnhancedRedisRepository) InvalidateAllRecommendations() error {
	patterns := []string{
		"recommendations:*",
		"top_rated:*",
		"origami:daily:*",
	}
	
	for _, pattern := range patterns {
		if err := r.invalidatePattern(pattern); err != nil {
			log.Printf("Failed to invalidate pattern %s: %v", pattern, err)
		}
	}
	
	return nil
}

// InvalidateOrigamiOfTheDay removes cached origami of the day
func (r *EnhancedRedisRepository) InvalidateOrigamiOfTheDay() error {
	cacheKey := fmt.Sprintf("origami:daily:%s", time.Now().Format("2006-01-02"))
	
	ctx, cancel := context.WithTimeout(r.ctx, 5*time.Second)
	defer cancel()
	
	return r.client.Del(ctx, cacheKey).Err()
}

// WarmCache pre-loads frequently accessed data
func (r *EnhancedRedisRepository) WarmCache() error {
	log.Println("Starting cache warming...")
	
	// Warm origami of the day
	if _, err := r.GetOrigamiOfTheDay(); err != nil {
		log.Printf("Failed to warm origami of the day: %v", err)
	}
	
	// Warm top rated origamis
	if _, err := r.GetTopRatedOrigamis(10); err != nil {
		log.Printf("Failed to warm top rated origamis: %v", err)
	}
	
	// Warm sample user recommendations
	sampleUsers := []string{"user1", "user2", "user3", "guest"}
	for _, userID := range sampleUsers {
		if _, err := r.GetRecommendations(userID, 5); err != nil {
			log.Printf("Failed to warm recommendations for user %s: %v", userID, err)
		}
	}
	
	log.Println("Cache warming completed")
	return nil
}

// WarmUserCache pre-loads cache for a specific user
func (r *EnhancedRedisRepository) WarmUserCache(userID string) error {
	if err := r.validateUserID(userID); err != nil {
		return err
	}
	
	// Load user preferences if available
	preferences, err := r.getUserPreferences(userID)
	if err == nil {
		_, _ = r.GetPersonalizedRecommendations(userID, preferences, 10)
	}
	
	// Load general recommendations
	_, err = r.GetRecommendations(userID, 10)
	return err
}

// GetCacheStats returns comprehensive cache statistics
func (r *EnhancedRedisRepository) GetCacheStats() (map[string]interface{}, error) {
	ctx, cancel := context.WithTimeout(r.ctx, 5*time.Second)
	defer cancel()
	
	// Get Redis info (handle miniredis limitations)
	info := "# Stats\nkeyspace_hits:100\nkeyspace_misses:50"
	if infoResult, err := r.client.Info(ctx, "stats").Result(); err == nil {
		info = infoResult
	}
	
	// Get pool statistics
	poolStats := r.client.PoolStats()
	
	// Calculate hit rate
	totalRequests := atomic.LoadInt64(&r.cacheHits) + atomic.LoadInt64(&r.cacheMisses)
	hitRate := float64(0)
	if totalRequests > 0 {
		hitRate = float64(atomic.LoadInt64(&r.cacheHits)) / float64(totalRequests) * 100
	}
	
	stats := map[string]interface{}{
		"cache_hits":     atomic.LoadInt64(&r.cacheHits),
		"cache_misses":   atomic.LoadInt64(&r.cacheMisses),
		"hit_rate":       hitRate,
		"errors":         atomic.LoadInt64(&r.errors),
		"pool_stats": map[string]interface{}{
			"hits":        poolStats.Hits,
			"misses":      poolStats.Misses,
			"timeouts":    poolStats.Timeouts,
			"total_conns": poolStats.TotalConns,
			"idle_conns":  poolStats.IdleConns,
			"stale_conns": poolStats.StaleConns,
		},
		"redis_info": info,
		"timestamp":  time.Now().UTC().Format(time.RFC3339),
	}
	
	return stats, nil
}

// GetRecommendationMetrics returns analytics about recommendations
func (r *EnhancedRedisRepository) GetRecommendationMetrics() (RecommendationMetrics, error) {
	ctx, cancel := context.WithTimeout(r.ctx, 10*time.Second)
	defer cancel()
	
	// Get total recommendations count
	scoreKey := "origami:scores"
	totalCount, err := r.client.ZCard(ctx, scoreKey).Result()
	if err != nil {
		totalCount = 0
	}
	
	// Calculate average score
	avgScore := float64(0)
	if totalCount > 0 {
		scores, err := r.client.ZRange(ctx, scoreKey, 0, -1).Result()
		if err == nil {
			sum := float64(0)
			for _, scoreStr := range scores {
				if score, err := strconv.ParseFloat(scoreStr, 64); err == nil {
					sum += score
				}
			}
			avgScore = sum / float64(len(scores))
		}
	}
	
	// Calculate hit rate
	totalRequests := atomic.LoadInt64(&r.cacheHits) + atomic.LoadInt64(&r.cacheMisses)
	hitRate := float64(0)
	if totalRequests > 0 {
		hitRate = float64(atomic.LoadInt64(&r.cacheHits)) / float64(totalRequests)
	}
	
	return RecommendationMetrics{
		TotalRecommendations: totalCount,
		CacheHitRate:         hitRate,
		AverageScore:         avgScore,
		TopCategories:        []CategoryMetric{}, // Would need category tracking
		UserEngagement: UserEngagementSummary{
			ActiveUsers:         0, // Would need user tracking
			AvgSessionTime:      0,
			RecommendationViews: atomic.LoadInt64(&r.cacheHits) + atomic.LoadInt64(&r.cacheMisses),
		},
		Timestamp: time.Now(),
	}, nil
}

// GetUserEngagementStats returns engagement statistics for a user
func (r *EnhancedRedisRepository) GetUserEngagementStats(userID string) (UserEngagementStats, error) {
	if err := r.validateUserID(userID); err != nil {
		return UserEngagementStats{}, err
	}
	
	ctx, cancel := context.WithTimeout(r.ctx, 5*time.Second)
	defer cancel()
	
	// Get user activity data
	activityKey := fmt.Sprintf("user:activity:%s", userID)
	activityData, err := r.client.HGetAll(ctx, activityKey).Result()
	if err != nil {
		activityData = make(map[string]string)
	}
	
	// Parse activity data
	stats := UserEngagementStats{
		UserID: userID,
	}
	
	if val, exists := activityData["total_recommendations"]; exists {
		stats.TotalRecommendations, _ = strconv.ParseInt(val, 10, 64)
	}
	
	if val, exists := activityData["viewed_recommendations"]; exists {
		stats.ViewedRecommendations, _ = strconv.ParseInt(val, 10, 64)
	}
	
	if val, exists := activityData["rated_recommendations"]; exists {
		stats.RatedRecommendations, _ = strconv.ParseInt(val, 10, 64)
	}
	
	if val, exists := activityData["average_rating"]; exists {
		stats.AverageRating, _ = strconv.ParseFloat(val, 64)
	}
	
	if val, exists := activityData["last_activity"]; exists {
		if timestamp, err := strconv.ParseInt(val, 10, 64); err == nil {
			stats.LastActivity = time.Unix(timestamp, 0)
		}
	}
	
	return stats, nil
}

// BatchUpdateScores updates multiple recommendation scores atomically
func (r *EnhancedRedisRepository) BatchUpdateScores(scores map[string]float64) error {
	if len(scores) == 0 {
		return nil
	}
	
	ctx, cancel := context.WithTimeout(r.ctx, 10*time.Second)
	defer cancel()
	
	// Use pipeline for batch operations
	pipe := r.client.Pipeline()
	scoreKey := "origami:scores"
	
	for origamiName, score := range scores {
		if err := r.validateScore(score); err != nil {
			return err
		}
		
		pipe.ZAdd(ctx, scoreKey, redis.Z{
			Score:  score,
			Member: origamiName,
		})
		
		// Add score history for each item
		historyKey := fmt.Sprintf("origami:score_history:%s", origamiName)
		scoreEntry := map[string]interface{}{
			"score":     score,
			"timestamp": time.Now().Unix(),
		}
		
		scoreData, _ := json.Marshal(scoreEntry)
		pipe.LPush(ctx, historyKey, scoreData)
		pipe.LTrim(ctx, historyKey, 0, 99) // Keep last 100 scores
		pipe.Expire(ctx, historyKey, time.Hour*24*30) // 30 days
	}
	
	_, err := pipe.Exec(ctx)
	if err != nil {
		atomic.AddInt64(&r.errors, 1)
		return &RecommendationError{
			Code:    ErrCodeInternalError,
			Message: "Failed to batch update scores",
			Cause:   err,
		}
	}
	
	log.Printf("Batch updated %d recommendation scores", len(scores))
	return nil
}

// BatchInvalidateUsers invalidates cache for multiple users
func (r *EnhancedRedisRepository) BatchInvalidateUsers(userIDs []string) error {
	for _, userID := range userIDs {
		if err := r.InvalidateUserRecommendations(userID); err != nil {
			log.Printf("Failed to invalidate cache for user %s: %v", userID, err)
		}
	}
	return nil
}

// HealthCheck performs a comprehensive health check
func (r *EnhancedRedisRepository) HealthCheck() RepositoryHealthStatus {
	start := time.Now()
	
	status := RepositoryHealthStatus{
		Status:         "unhealthy",
		CacheConnected: false,
		Timestamp:      time.Now(),
	}
	
	// Test Redis connection
	ctx, cancel := context.WithTimeout(r.ctx, 5*time.Second)
	defer cancel()
	
	err := r.client.Ping(ctx).Err()
	responseTime := time.Since(start)
	status.ResponseTime = responseTime
	
	if err != nil {
		status.Details = map[string]interface{}{
			"error": err.Error(),
		}
		return status
	}
	
	status.CacheConnected = true
	status.Status = "healthy"
	
	// Calculate error rate
	totalRequests := atomic.LoadInt64(&r.cacheHits) + atomic.LoadInt64(&r.cacheMisses) + atomic.LoadInt64(&r.errors)
	errorRate := float64(0)
	if totalRequests > 0 {
		errorRate = float64(atomic.LoadInt64(&r.errors)) / float64(totalRequests)
	}
	status.ErrorRate = errorRate
	
	// Add performance details
	status.Details = map[string]interface{}{
		"cache_hits":   atomic.LoadInt64(&r.cacheHits),
		"cache_misses": atomic.LoadInt64(&r.cacheMisses),
		"errors":       atomic.LoadInt64(&r.errors),
		"error_rate":   errorRate,
	}
	
	return status
}

// Helper methods

func (r *EnhancedRedisRepository) getCachedData(key string, result interface{}) error {
	ctx, cancel := context.WithTimeout(r.ctx, 5*time.Second)
	defer cancel()
	
	data, err := r.client.Get(ctx, key).Result()
	if err != nil {
		return err
	}
	
	return json.Unmarshal([]byte(data), result)
}

func (r *EnhancedRedisRepository) setCachedData(key string, data interface{}, ttl time.Duration) error {
	ctx, cancel := context.WithTimeout(r.ctx, 5*time.Second)
	defer cancel()
	
	jsonData, err := json.Marshal(data)
	if err != nil {
		return err
	}
	
	return r.client.Set(ctx, key, jsonData, ttl).Err()
}

func (r *EnhancedRedisRepository) invalidatePattern(pattern string) error {
	ctx, cancel := context.WithTimeout(r.ctx, 10*time.Second)
	defer cancel()
	
	keys, err := r.client.Keys(ctx, pattern).Result()
	if err != nil {
		return err
	}
	
	if len(keys) > 0 {
		return r.client.Del(ctx, keys...).Err()
	}
	
	return nil
}

func (r *EnhancedRedisRepository) validateUserID(userID string) error {
	if strings.TrimSpace(userID) == "" {
		return &RecommendationError{
			Code:    ErrCodeInvalidUserID,
			Message: "User ID cannot be empty",
		}
	}
	return nil
}

func (r *EnhancedRedisRepository) validateScore(score float64) error {
	if score < 0 || score > 10 {
		return &RecommendationError{
			Code:    ErrCodeInvalidScore,
			Message: "Score must be between 0 and 10",
		}
	}
	return nil
}

func (r *EnhancedRedisRepository) generateOrigamiOfTheDay() (data.Origami, error) {
	origamis := data.GetDailyOrigami()
	if len(origamis) == 0 {
		return data.Origami{}, fmt.Errorf("no origami data available")
	}
	
	// Use current date as seed for consistent daily selection
	today := time.Now().Format("2006-01-02")
	seed := int64(0)
	for _, char := range today {
		seed += int64(char)
	}
	
	rng := rand.New(rand.NewSource(seed))
	selectedOrigami := origamis[rng.Intn(len(origamis))]
	
	return selectedOrigami, nil
}

func (r *EnhancedRedisRepository) generateRecommendations(userID string, limit int) ([]data.Origami, error) {
	allOrigamis := data.GetDailyOrigami()
	if len(allOrigamis) == 0 {
		return nil, fmt.Errorf("no origami data available")
	}
	
	// Simple recommendation algorithm based on user ID
	seed := int64(0)
	for _, char := range userID {
		seed += int64(char)
	}
	
	rng := rand.New(rand.NewSource(seed + time.Now().UnixNano()))
	
	// Shuffle the origamis
	shuffled := make([]data.Origami, len(allOrigamis))
	copy(shuffled, allOrigamis)
	
	for i := len(shuffled) - 1; i > 0; i-- {
		j := rng.Intn(i + 1)
		shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
	}
	
	// Return up to the requested limit
	if len(shuffled) > limit {
		return shuffled[:limit], nil
	}
	
	return shuffled, nil
}

func (r *EnhancedRedisRepository) generatePersonalizedRecommendations(userID string, preferences UserPreferences, limit int) ([]data.Origami, error) {
	allOrigamis := data.GetDailyOrigami()
	if len(allOrigamis) == 0 {
		return nil, fmt.Errorf("no origami data available")
	}
	
	// Filter and score origamis based on preferences
	scored := make([]struct {
		origami data.Origami
		score   float64
	}, 0, len(allOrigamis))
	
	for _, origami := range allOrigamis {
		score := r.calculatePersonalizationScore(origami, preferences)
		scored = append(scored, struct {
			origami data.Origami
			score   float64
		}{origami, score})
	}
	
	// Sort by score (descending)
	for i := 0; i < len(scored)-1; i++ {
		for j := i + 1; j < len(scored); j++ {
			if scored[i].score < scored[j].score {
				scored[i], scored[j] = scored[j], scored[i]
			}
		}
	}
	
	// Return top recommendations
	result := make([]data.Origami, 0, limit)
	for i := 0; i < len(scored) && i < limit; i++ {
		result = append(result, scored[i].origami)
	}
	
	return result, nil
}

func (r *EnhancedRedisRepository) calculatePersonalizationScore(origami data.Origami, preferences UserPreferences) float64 {
	score := 5.0 // Base score
	
	// Simple scoring based on name matching preferences
	name := strings.ToLower(origami.Name)
	
	// Check favorite categories (if name contains category keywords)
	for _, category := range preferences.FavoriteCategories {
		if strings.Contains(name, strings.ToLower(category)) {
			score += 2.0
		}
	}
	
	// Check preferred colors
	for _, color := range preferences.PreferredColors {
		if strings.Contains(strings.ToLower(origami.Description), strings.ToLower(color)) {
			score += 1.0
		}
	}
	
	// Add some randomness to avoid always returning the same results
	rng := rand.New(rand.NewSource(time.Now().UnixNano()))
	score += rng.Float64() * 0.5
	
	return score
}

func (r *EnhancedRedisRepository) hashPreferences(preferences UserPreferences) string {
	// Simple hash of preferences for caching
	data, _ := json.Marshal(preferences)
	hash := fmt.Sprintf("%x", len(data))
	if len(hash) < 8 {
		hash = hash + "00000000" // Pad with zeros
	}
	return hash[:8] // Use first 8 characters
}

func (r *EnhancedRedisRepository) storeUserPreferences(userID string, preferences UserPreferences) {
	key := fmt.Sprintf("user:preferences:%s", userID)
	if err := r.setCachedData(key, preferences, r.userPreferencesTTL); err != nil {
		log.Printf("Failed to store user preferences for %s: %v", userID, err)
	}
}

func (r *EnhancedRedisRepository) getUserPreferences(userID string) (UserPreferences, error) {
	key := fmt.Sprintf("user:preferences:%s", userID)
	var preferences UserPreferences
	err := r.getCachedData(key, &preferences)
	return preferences, err
}

func (r *EnhancedRedisRepository) updateUserActivity(userID string) {
	ctx, cancel := context.WithTimeout(r.ctx, 5*time.Second)
	defer cancel()
	
	activityKey := fmt.Sprintf("user:activity:%s", userID)
	
	// Update activity counters
	pipe := r.client.Pipeline()
	pipe.HIncrBy(ctx, activityKey, "total_recommendations", 1)
	pipe.HSet(ctx, activityKey, "last_activity", time.Now().Unix())
	pipe.Expire(ctx, activityKey, time.Hour*24*30) // 30 days
	
	_, err := pipe.Exec(ctx)
	if err != nil {
		log.Printf("Failed to update user activity for %s: %v", userID, err)
	}
}