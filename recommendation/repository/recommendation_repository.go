package repository

import (
	"context"
	"fmt"
	"log"
	"math/rand"
	"recommendation/data"
	"recommendation/database"
	"time"
)

// RecommendationRepository handles caching and retrieval of recommendations
type RecommendationRepository struct {
	redisManager *database.RedisManager
}

// NewRecommendationRepository creates a new recommendation repository
func NewRecommendationRepository(redisManager *database.RedisManager) *RecommendationRepository {
	return &RecommendationRepository{
		redisManager: redisManager,
	}
}

// GetOrigamiOfTheDay returns the origami of the day, using cache when available
func (r *RecommendationRepository) GetOrigamiOfTheDay() (data.Origami, error) {
	// Try to get from cache first
	var cachedOrigami data.Origami
	err := r.redisManager.GetOrigamiOfTheDay(&cachedOrigami)
	
	if err == nil {
		log.Println("Returning cached origami of the day")
		return cachedOrigami, nil
	}

	// If not in cache or cache miss, generate new recommendation
	log.Printf("Cache miss for origami of the day: %v", err)
	origami, err := r.generateOrigamiOfTheDay()
	if err != nil {
		return data.Origami{}, fmt.Errorf("failed to generate origami of the day: %w", err)
	}

	// Cache the result
	if cacheErr := r.redisManager.SetOrigamiOfTheDay(origami); cacheErr != nil {
		log.Printf("Failed to cache origami of the day: %v", cacheErr)
		// Don't fail the request if caching fails, just log the error
	}

	return origami, nil
}

// generateOrigamiOfTheDay generates a new origami recommendation for the day
func (r *RecommendationRepository) generateOrigamiOfTheDay() (data.Origami, error) {
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
	
	rand.Seed(seed)
	selectedOrigami := origamis[rand.Intn(len(origamis))]
	
	log.Printf("Generated new origami of the day: %s", selectedOrigami.Name)
	return selectedOrigami, nil
}

// GetRecommendations returns personalized recommendations based on user preferences
func (r *RecommendationRepository) GetRecommendations(userID string, limit int) ([]data.Origami, error) {
	cacheKey := fmt.Sprintf("recommendations:user:%s", userID)
	
	// Try to get from cache
	var cachedRecommendations []data.Origami
	err := r.redisManager.GetRecommendation(cacheKey, &cachedRecommendations)
	
	if err == nil && len(cachedRecommendations) > 0 {
		log.Printf("Returning cached recommendations for user %s", userID)
		if len(cachedRecommendations) > limit {
			return cachedRecommendations[:limit], nil
		}
		return cachedRecommendations, nil
	}

	// Generate new recommendations
	log.Printf("Generating new recommendations for user %s", userID)
	recommendations, err := r.generateRecommendations(userID, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to generate recommendations: %w", err)
	}

	// Cache the recommendations for 1 hour
	if cacheErr := r.redisManager.SetRecommendation(cacheKey, recommendations, time.Hour); cacheErr != nil {
		log.Printf("Failed to cache recommendations for user %s: %v", userID, cacheErr)
	}

	return recommendations, nil
}

// generateRecommendations generates personalized recommendations for a user
func (r *RecommendationRepository) generateRecommendations(userID string, limit int) ([]data.Origami, error) {
	allOrigamis := data.GetDailyOrigami()
	if len(allOrigamis) == 0 {
		return nil, fmt.Errorf("no origami data available")
	}

	// Simple recommendation algorithm - in a real system, this would be more sophisticated
	// For now, we'll return a shuffled list based on user ID as seed
	seed := int64(0)
	for _, char := range userID {
		seed += int64(char)
	}
	
	rand.Seed(seed + time.Now().Unix())
	
	// Shuffle the origamis
	shuffled := make([]data.Origami, len(allOrigamis))
	copy(shuffled, allOrigamis)
	
	for i := len(shuffled) - 1; i > 0; i-- {
		j := rand.Intn(i + 1)
		shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
	}

	// Return up to the requested limit
	if len(shuffled) > limit {
		return shuffled[:limit], nil
	}
	
	return shuffled, nil
}

// UpdateRecommendationScore updates the score for a recommendation
func (r *RecommendationRepository) UpdateRecommendationScore(origamiName string, score float64) error {
	scoreKey := "origami:scores"
	return r.redisManager.SetRecommendationScore(scoreKey, origamiName, score)
}

// GetTopRatedOrigamis returns the top-rated origamis
func (r *RecommendationRepository) GetTopRatedOrigamis(limit int) ([]string, error) {
	scoreKey := "origami:scores"
	return r.redisManager.GetTopRecommendations(scoreKey, int64(limit))
}

// InvalidateUserRecommendations removes cached recommendations for a user
func (r *RecommendationRepository) InvalidateUserRecommendations(userID string) error {
	cacheKey := fmt.Sprintf("recommendations:user:%s", userID)
	return r.redisManager.DeleteRecommendation(cacheKey)
}

// InvalidateAllRecommendations removes all cached recommendations
func (r *RecommendationRepository) InvalidateAllRecommendations() error {
	return r.redisManager.InvalidateCache("recommendations:*")
}

// GetCacheStats returns statistics about the recommendation cache
func (r *RecommendationRepository) GetCacheStats() (map[string]interface{}, error) {
	client := r.redisManager.GetClient()
	ctx := context.Background()
	
	// Get cache statistics
	info, err := client.Info(ctx, "stats").Result()
	if err != nil {
		return nil, fmt.Errorf("failed to get cache stats: %w", err)
	}

	// Parse the info string and extract relevant statistics
	stats := make(map[string]interface{})
	
	// Add pool statistics
	poolStats := r.redisManager.HealthCheck().Database.PoolStats
	if poolStats != nil {
		stats["pool_stats"] = poolStats
	}
	
	// Add basic info
	stats["info"] = info
	stats["timestamp"] = time.Now().UTC().Format(time.RFC3339)
	
	return stats, nil
}

// WarmCache pre-loads frequently accessed data into the cache
func (r *RecommendationRepository) WarmCache() error {
	log.Println("Warming recommendation cache...")
	
	// Pre-generate origami of the day
	_, err := r.GetOrigamiOfTheDay()
	if err != nil {
		log.Printf("Failed to warm origami of the day cache: %v", err)
	}
	
	// Pre-generate some sample user recommendations
	sampleUsers := []string{"user1", "user2", "user3"}
	for _, userID := range sampleUsers {
		_, err := r.GetRecommendations(userID, 5)
		if err != nil {
			log.Printf("Failed to warm recommendations cache for user %s: %v", userID, err)
		}
	}
	
	log.Println("Cache warming completed")
	return nil
}