package main

import (
	"encoding/json"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"recommendation/api"
	"recommendation/database"
	"recommendation/repository"

	"github.com/gin-gonic/gin"
)

// Config represents the structure of our configuration file.
type Config struct {
	Version string `json:"version"`
}

// App holds the application dependencies
type App struct {
	RedisManager *database.RedisManager
	Repository   *repository.RecommendationRepository
	Config       Config
}

// loadConfig reads the configuration file and returns a Config struct.
func loadConfig() (Config, error) {
	file, err := os.Open("config.json")
	if err != nil {
		return Config{}, err
	}
	defer file.Close()

	config := Config{}
	decoder := json.NewDecoder(file)
	err = decoder.Decode(&config)
	return config, err
}

type SystemInfo struct {
	Hostname     string
	IPAddress    string
	IsContainer  bool
	IsKubernetes bool
}

func GetSystemInfo() SystemInfo {
	hostname, _ := os.Hostname()
	addrs, _ := net.InterfaceAddrs()
	ip := ""
	for _, addr := range addrs {
		if ipnet, ok := addr.(*net.IPNet); ok && !ipnet.IP.IsLoopback() {
			if ipnet.IP.To4() != nil {
				ip = ipnet.IP.String()
				break
			}
		}
	}
	isContainer := false
	if _, err := os.Stat("/.dockerenv"); err == nil {
		isContainer = true
	}
	isKubernetes := false

	return SystemInfo{
		Hostname:     hostname,
		IPAddress:    ip,
		IsContainer:  isContainer,
		IsKubernetes: isKubernetes,
	}
}

// setupApp initializes the application dependencies
func setupApp() (*App, error) {
	// Load configuration
	config, err := loadConfig()
	if err != nil {
		return nil, err
	}

	// Initialize Redis manager
	redisManager, err := database.NewRedisManager()
	if err != nil {
		log.Printf("Warning: Failed to initialize Redis manager: %v", err)
		log.Println("Application will continue without caching capabilities")
		// Continue without Redis for development/testing
		redisManager = nil
	}

	// Initialize repository
	var repo *repository.RecommendationRepository
	if redisManager != nil {
		repo = repository.NewRecommendationRepository(redisManager)
		// Warm the cache on startup
		go func() {
			if err := repo.WarmCache(); err != nil {
				log.Printf("Failed to warm cache: %v", err)
			}
		}()
	}

	return &App{
		RedisManager: redisManager,
		Repository:   repo,
		Config:       config,
	}, nil
}

// getRecommendationStatus returns the health status of the recommendation service
func (app *App) getRecommendationStatus(c *gin.Context) {
	status := "operational"
	details := make(map[string]interface{})

	// Check Redis health if available
	if app.RedisManager != nil {
		redisHealth := app.RedisManager.HealthCheck()
		details["redis"] = redisHealth
		
		if redisHealth.Status != "healthy" {
			status = "degraded"
		}
	} else {
		details["redis"] = map[string]interface{}{
			"status": "unavailable",
			"message": "Redis not configured",
		}
		status = "degraded"
	}

	// Add system information
	details["system"] = GetSystemInfo()
	details["timestamp"] = time.Now().UTC().Format(time.RFC3339)

	c.JSON(http.StatusOK, gin.H{
		"status":  status,
		"details": details,
	})
}

// getHealthCheck returns detailed health information
func (app *App) getHealthCheck(c *gin.Context) {
	health := make(map[string]interface{})
	
	// Overall status
	overallStatus := "healthy"
	
	// Redis health
	if app.RedisManager != nil {
		redisHealth := app.RedisManager.HealthCheck()
		health["redis"] = redisHealth
		
		if redisHealth.Status != "healthy" {
			overallStatus = "degraded"
		}
	} else {
		health["redis"] = map[string]interface{}{
			"status": "unavailable",
			"message": "Redis not configured - running in fallback mode",
		}
	}

	// Application health
	health["application"] = map[string]interface{}{
		"status": "healthy",
		"version": app.Config.Version,
		"uptime": time.Since(startTime).String(),
	}

	health["status"] = overallStatus
	health["timestamp"] = time.Now().UTC().Format(time.RFC3339)

	c.JSON(http.StatusOK, health)
}

func (app *App) renderHomePage(c *gin.Context) {
	systemInfo := GetSystemInfo()

	c.HTML(http.StatusOK, "index.html", gin.H{
		"Year":       time.Now().Year(),
		"Version":    app.Config.Version,
		"SystemInfo": systemInfo,
	})
}

var startTime time.Time

func main() {
	startTime = time.Now()
	
	// Initialize application
	app, err := setupApp()
	if err != nil {
		log.Fatalf("Failed to setup application: %v", err)
	}

	// Setup graceful shutdown
	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt, syscall.SIGTERM)

	go func() {
		<-c
		log.Println("Shutting down gracefully...")
		
		if app.RedisManager != nil {
			if err := app.RedisManager.Close(); err != nil {
				log.Printf("Error closing Redis connection: %v", err)
			}
		}
		
		os.Exit(0)
	}()

	// Setup router
	router := gin.Default()

	// Load HTML files
	router.LoadHTMLGlob("templates/*")

	// Set path to serve static files
	router.Static("/static", "./static")

	// Define route for the home page
	router.GET("/", app.renderHomePage)

	// API routes
	apiGroup := router.Group("/api")
	{
		// Initialize API with repository if available
		if app.Repository != nil {
			api.InitializeWithRepository(app.Repository)
		}
		
		apiGroup.GET("/origami-of-the-day", api.GetOrigamiOfTheDay)
		apiGroup.GET("/recommendations/:userID", api.GetRecommendations)
		apiGroup.POST("/recommendations/:origami/score", api.UpdateScore)
		apiGroup.GET("/top-rated", api.GetTopRated)
		
		// Health and status endpoints
		apiGroup.GET("/recommendation-status", app.getRecommendationStatus)
		apiGroup.GET("/health", app.getHealthCheck)
		
		// Cache management endpoints (admin only in production)
		apiGroup.POST("/cache/invalidate", api.InvalidateCache)
		apiGroup.GET("/cache/stats", api.GetCacheStats)
	}

	log.Printf("Starting recommendation service on port 8080...")
	log.Printf("Redis enabled: %t", app.RedisManager != nil)
	
	// Start the server on port 8080
	if err := router.Run(":8080"); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}


