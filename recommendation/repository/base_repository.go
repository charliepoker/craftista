package repository

import (
	"fmt"
	"recommendation/data"
	"time"
)

// RecommendationRepositoryInterface defines the contract for recommendation repository operations
type RecommendationRepositoryInterface interface {
	// Core recommendation methods
	GetOrigamiOfTheDay() (data.Origami, error)
	GetRecommendations(userID string, limit int) ([]data.Origami, error)
	GetPersonalizedRecommendations(userID string, preferences UserPreferences, limit int) ([]data.Origami, error)
	
	// Scoring and ranking methods
	UpdateRecommendationScore(origamiName string, score float64) error
	GetTopRatedOrigamis(limit int) ([]string, error)
	GetRecommendationsByScore(minScore float64, limit int) ([]data.Origami, error)
	
	// Cache management methods
	InvalidateUserRecommendations(userID string) error
	InvalidateAllRecommendations() error
	InvalidateOrigamiOfTheDay() error
	WarmCache() error
	WarmUserCache(userID string) error
	
	// Analytics and statistics methods
	GetCacheStats() (map[string]interface{}, error)
	GetRecommendationMetrics() (RecommendationMetrics, error)
	GetUserEngagementStats(userID string) (UserEngagementStats, error)
	
	// Batch operations
	BatchUpdateScores(scores map[string]float64) error
	BatchInvalidateUsers(userIDs []string) error
	
	// Health and monitoring
	HealthCheck() RepositoryHealthStatus
}

// UserPreferences represents user preferences for personalized recommendations
type UserPreferences struct {
	FavoriteCategories []string          `json:"favorite_categories"`
	DifficultyLevel    string            `json:"difficulty_level"`
	PreferredColors    []string          `json:"preferred_colors"`
	CustomAttributes   map[string]string `json:"custom_attributes"`
}

// RecommendationMetrics contains analytics data about recommendations
type RecommendationMetrics struct {
	TotalRecommendations int64                  `json:"total_recommendations"`
	CacheHitRate         float64                `json:"cache_hit_rate"`
	AverageScore         float64                `json:"average_score"`
	TopCategories        []CategoryMetric       `json:"top_categories"`
	UserEngagement       UserEngagementSummary  `json:"user_engagement"`
	Timestamp            time.Time              `json:"timestamp"`
}

// CategoryMetric represents metrics for a specific category
type CategoryMetric struct {
	Category string  `json:"category"`
	Count    int64   `json:"count"`
	AvgScore float64 `json:"avg_score"`
}

// UserEngagementSummary contains overall user engagement statistics
type UserEngagementSummary struct {
	ActiveUsers     int64   `json:"active_users"`
	AvgSessionTime  float64 `json:"avg_session_time"`
	RecommendationViews int64 `json:"recommendation_views"`
}

// UserEngagementStats contains detailed engagement statistics for a specific user
type UserEngagementStats struct {
	UserID              string    `json:"user_id"`
	TotalRecommendations int64     `json:"total_recommendations"`
	ViewedRecommendations int64    `json:"viewed_recommendations"`
	RatedRecommendations int64     `json:"rated_recommendations"`
	AverageRating       float64   `json:"average_rating"`
	LastActivity        time.Time `json:"last_activity"`
	PreferredCategories []string  `json:"preferred_categories"`
}

// RepositoryHealthStatus represents the health status of the repository
type RepositoryHealthStatus struct {
	Status           string                 `json:"status"`
	CacheConnected   bool                   `json:"cache_connected"`
	ResponseTime     time.Duration          `json:"response_time"`
	ErrorRate        float64                `json:"error_rate"`
	Details          map[string]interface{} `json:"details"`
	Timestamp        time.Time              `json:"timestamp"`
}

// CacheStrategy defines different caching strategies
type CacheStrategy int

const (
	CacheStrategyLRU CacheStrategy = iota
	CacheStrategyTTL
	CacheStrategyWriteThrough
	CacheStrategyWriteBehind
)

// RecommendationError represents errors that can occur in recommendation operations
type RecommendationError struct {
	Code    string `json:"code"`
	Message string `json:"message"`
	Cause   error  `json:"-"`
}

func (e *RecommendationError) Error() string {
	if e.Cause != nil {
		return fmt.Sprintf("%s: %s (caused by: %v)", e.Code, e.Message, e.Cause)
	}
	return fmt.Sprintf("%s: %s", e.Code, e.Message)
}

// Error codes for recommendation operations
const (
	ErrCodeCacheUnavailable    = "CACHE_UNAVAILABLE"
	ErrCodeInvalidUserID       = "INVALID_USER_ID"
	ErrCodeInvalidScore        = "INVALID_SCORE"
	ErrCodeRecommendationNotFound = "RECOMMENDATION_NOT_FOUND"
	ErrCodeInternalError       = "INTERNAL_ERROR"
)