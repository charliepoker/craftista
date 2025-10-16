package api

import (
	"log"
	"math/rand"
	"net/http"
	"recommendation/data"
	"recommendation/repository"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
)

var repo *repository.RecommendationRepository

// InitializeWithRepository sets the repository for the API handlers
func InitializeWithRepository(r *repository.RecommendationRepository) {
	repo = r
}

// GetOrigamiOfTheDay returns the origami of the day, using cache when available
func GetOrigamiOfTheDay(c *gin.Context) {
	var origami data.Origami
	var err error

	// Use repository if available, otherwise fallback to direct data access
	if repo != nil {
		origami, err = repo.GetOrigamiOfTheDay()
		if err != nil {
			log.Printf("Repository error, falling back to direct access: %v", err)
			origami, err = getOrigamiDirectly()
		}
	} else {
		origami, err = getOrigamiDirectly()
	}

	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to get origami of the day",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, origami)
}

// getOrigamiDirectly gets origami without caching (fallback method)
func getOrigamiDirectly() (data.Origami, error) {
	origamis := data.GetDailyOrigami()
	if len(origamis) == 0 {
		return data.Origami{}, gin.Error{Err: gin.Error{}.Err, Type: gin.ErrorTypePublic}
	}

	// Use current date as seed for consistent daily selection
	today := time.Now().Format("2006-01-02")
	seed := int64(0)
	for _, char := range today {
		seed += int64(char)
	}
	
	rand.Seed(seed)
	selectedOrigami := origamis[rand.Intn(len(origamis))]
	
	return selectedOrigami, nil
}

// GetRecommendations returns personalized recommendations for a user
func GetRecommendations(c *gin.Context) {
	userID := c.Param("userID")
	if userID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "User ID is required",
		})
		return
	}

	// Parse limit parameter
	limitStr := c.DefaultQuery("limit", "5")
	limit, err := strconv.Atoi(limitStr)
	if err != nil || limit <= 0 {
		limit = 5
	}
	if limit > 20 {
		limit = 20 // Cap at 20 recommendations
	}

	var recommendations []data.Origami

	// Use repository if available, otherwise fallback to direct data access
	if repo != nil {
		recommendations, err = repo.GetRecommendations(userID, limit)
		if err != nil {
			log.Printf("Repository error, falling back to direct access: %v", err)
			recommendations = getRecommendationsDirectly(userID, limit)
		}
	} else {
		recommendations = getRecommendationsDirectly(userID, limit)
	}

	c.JSON(http.StatusOK, gin.H{
		"user_id": userID,
		"recommendations": recommendations,
		"count": len(recommendations),
	})
}

// getRecommendationsDirectly gets recommendations without caching (fallback method)
func getRecommendationsDirectly(userID string, limit int) []data.Origami {
	allOrigamis := data.GetDailyOrigami()
	if len(allOrigamis) == 0 {
		return []data.Origami{}
	}

	// Simple recommendation algorithm based on user ID
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
		return shuffled[:limit]
	}
	
	return shuffled
}

// UpdateScore updates the score for an origami recommendation
func UpdateScore(c *gin.Context) {
	origamiName := c.Param("origami")
	if origamiName == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Origami name is required",
		})
		return
	}

	var scoreData struct {
		Score float64 `json:"score" binding:"required"`
	}

	if err := c.ShouldBindJSON(&scoreData); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid score data",
			"details": err.Error(),
		})
		return
	}

	// Validate score range
	if scoreData.Score < 0 || scoreData.Score > 10 {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Score must be between 0 and 10",
		})
		return
	}

	// Update score if repository is available
	if repo != nil {
		if err := repo.UpdateRecommendationScore(origamiName, scoreData.Score); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": "Failed to update score",
				"details": err.Error(),
			})
			return
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "Score updated successfully",
		"origami": origamiName,
		"score": scoreData.Score,
	})
}

// GetTopRated returns the top-rated origamis
func GetTopRated(c *gin.Context) {
	// Parse limit parameter
	limitStr := c.DefaultQuery("limit", "10")
	limit, err := strconv.Atoi(limitStr)
	if err != nil || limit <= 0 {
		limit = 10
	}
	if limit > 50 {
		limit = 50 // Cap at 50 results
	}

	var topRated []string

	// Use repository if available
	if repo != nil {
		topRated, err = repo.GetTopRatedOrigamis(limit)
		if err != nil {
			log.Printf("Failed to get top rated origamis: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{
				"error": "Failed to get top rated origamis",
				"details": err.Error(),
			})
			return
		}
	} else {
		// Fallback: return all origami names
		origamis := data.GetDailyOrigami()
		for i, origami := range origamis {
			if i >= limit {
				break
			}
			topRated = append(topRated, origami.Name)
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"top_rated": topRated,
		"count": len(topRated),
	})
}

// InvalidateCache invalidates cached recommendations
func InvalidateCache(c *gin.Context) {
	var invalidateData struct {
		UserID string `json:"user_id"`
		All    bool   `json:"all"`
	}

	if err := c.ShouldBindJSON(&invalidateData); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Invalid invalidation data",
			"details": err.Error(),
		})
		return
	}

	if repo == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error": "Cache not available",
		})
		return
	}

	var err error
	if invalidateData.All {
		err = repo.InvalidateAllRecommendations()
	} else if invalidateData.UserID != "" {
		err = repo.InvalidateUserRecommendations(invalidateData.UserID)
	} else {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Either user_id or all=true must be specified",
		})
		return
	}

	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to invalidate cache",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "Cache invalidated successfully",
	})
}

// GetCacheStats returns cache statistics
func GetCacheStats(c *gin.Context) {
	if repo == nil {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error": "Cache not available",
		})
		return
	}

	stats, err := repo.GetCacheStats()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to get cache stats",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, stats)
}

// InitRouter initializes the routes and returns a gin.Engine instance
func InitRouter() *gin.Engine {
	r := gin.Default()
	
	// Basic routes
	r.GET("/origami-of-the-day", GetOrigamiOfTheDay)
	r.GET("/recommendations/:userID", GetRecommendations)
	r.POST("/recommendations/:origami/score", UpdateScore)
	r.GET("/top-rated", GetTopRated)
	
	// Cache management routes
	r.POST("/cache/invalidate", InvalidateCache)
	r.GET("/cache/stats", GetCacheStats)

	return r
}

// StartAPI starts the server on port 8080
func StartAPI() {
	router := InitRouter()
	router.Run(":8080")
}