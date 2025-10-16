package database

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"
)

// CircuitBreakerState represents the current state of the circuit breaker
type CircuitBreakerState int

const (
	// StateClosed - Normal operation, requests are allowed
	StateClosed CircuitBreakerState = iota
	// StateOpen - Failing, requests are rejected
	StateOpen
	// StateHalfOpen - Testing if service recovered
	StateHalfOpen
)

// String returns the string representation of the circuit breaker state
func (s CircuitBreakerState) String() string {
	switch s {
	case StateClosed:
		return "CLOSED"
	case StateOpen:
		return "OPEN"
	case StateHalfOpen:
		return "HALF_OPEN"
	default:
		return "UNKNOWN"
	}
}

// CircuitBreakerConfig holds the configuration for circuit breaker behavior
type CircuitBreakerConfig struct {
	FailureThreshold   int           // Number of failures before opening
	RecoveryTimeout    time.Duration // Time before trying half-open
	SuccessThreshold   int           // Successes needed to close from half-open
	Timeout           time.Duration // Operation timeout
	MaxRequests       int           // Max requests allowed in half-open state
}

// DefaultCircuitBreakerConfig returns a default configuration
func DefaultCircuitBreakerConfig() *CircuitBreakerConfig {
	return &CircuitBreakerConfig{
		FailureThreshold: 5,
		RecoveryTimeout:  60 * time.Second,
		SuccessThreshold: 3,
		Timeout:         30 * time.Second,
		MaxRequests:     3,
	}
}

// CircuitBreakerError represents an error when circuit breaker is open
type CircuitBreakerError struct {
	Message string
	State   CircuitBreakerState
}

func (e *CircuitBreakerError) Error() string {
	return e.Message
}

// StateChange represents a circuit breaker state change event
type StateChange struct {
	Timestamp    time.Time `json:"timestamp"`
	FromState    string    `json:"from_state"`
	ToState      string    `json:"to_state"`
	FailureCount int       `json:"failure_count"`
	TotalFailures int      `json:"total_failures"`
}

// Metrics holds circuit breaker metrics for monitoring
type Metrics struct {
	Name              string         `json:"name"`
	State             string         `json:"state"`
	FailureCount      int            `json:"failure_count"`
	SuccessCount      int            `json:"success_count"`
	TotalRequests     int64          `json:"total_requests"`
	TotalFailures     int64          `json:"total_failures"`
	TotalSuccesses    int64          `json:"total_successes"`
	FailureRate       float64        `json:"failure_rate_percent"`
	LastFailureTime   *time.Time     `json:"last_failure_time,omitempty"`
	NextAttemptTime   *time.Time     `json:"next_attempt_time,omitempty"`
	Config            *CircuitBreakerConfig `json:"config"`
	RecentStateChanges []StateChange `json:"recent_state_changes"`
}

// CircuitBreaker implements the circuit breaker pattern for database operations
type CircuitBreaker struct {
	name            string
	config          *CircuitBreakerConfig
	state           CircuitBreakerState
	failureCount    int
	successCount    int
	totalRequests   int64
	totalFailures   int64
	totalSuccesses  int64
	lastFailureTime *time.Time
	nextAttemptTime *time.Time
	stateChanges    []StateChange
	mutex           sync.RWMutex
}

// NewCircuitBreaker creates a new circuit breaker instance
func NewCircuitBreaker(name string, config *CircuitBreakerConfig) *CircuitBreaker {
	if config == nil {
		config = DefaultCircuitBreakerConfig()
	}

	cb := &CircuitBreaker{
		name:         name,
		config:       config,
		state:        StateClosed,
		stateChanges: make([]StateChange, 0),
	}

	log.Printf("Circuit breaker '%s' initialized with config: %+v", name, config)
	return cb
}

// Execute runs an operation through the circuit breaker
func (cb *CircuitBreaker) Execute(ctx context.Context, operation func(context.Context) (interface{}, error)) (interface{}, error) {
	if !cb.canAttempt() {
		return nil, &CircuitBreakerError{
			Message: fmt.Sprintf("Circuit breaker '%s' is %s. Next attempt allowed at %v",
				cb.name, cb.state.String(), cb.nextAttemptTime),
			State: cb.state,
		}
	}

	// Create context with timeout
	timeoutCtx, cancel := context.WithTimeout(ctx, cb.config.Timeout)
	defer cancel()

	// Execute operation
	result, err := operation(timeoutCtx)

	if err != nil {
		cb.recordFailure()
		return nil, err
	}

	cb.recordSuccess()
	return result, nil
}

// canAttempt checks if an operation attempt is allowed
func (cb *CircuitBreaker) canAttempt() bool {
	cb.mutex.Lock()
	defer cb.mutex.Unlock()

	switch cb.state {
	case StateClosed:
		return true
	case StateOpen:
		if cb.nextAttemptTime != nil && time.Now().After(*cb.nextAttemptTime) {
			cb.transitionToHalfOpen()
			return true
		}
		return false
	case StateHalfOpen:
		return true
	}
	return false
}

// recordSuccess records a successful operation
func (cb *CircuitBreaker) recordSuccess() {
	cb.mutex.Lock()
	defer cb.mutex.Unlock()

	cb.totalRequests++
	cb.totalSuccesses++
	cb.failureCount = 0

	if cb.state == StateHalfOpen {
		cb.successCount++
		if cb.successCount >= cb.config.SuccessThreshold {
			cb.transitionToClosed()
		}
	}

	log.Printf("Circuit breaker '%s': Success recorded", cb.name)
}

// recordFailure records a failed operation
func (cb *CircuitBreaker) recordFailure() {
	cb.mutex.Lock()
	defer cb.mutex.Unlock()

	cb.totalRequests++
	cb.totalFailures++
	cb.failureCount++
	cb.successCount = 0
	now := time.Now()
	cb.lastFailureTime = &now

	if (cb.state == StateClosed && cb.failureCount >= cb.config.FailureThreshold) ||
		cb.state == StateHalfOpen {
		cb.transitionToOpen()
	}

	log.Printf("Circuit breaker '%s': Failure recorded (count: %d)", cb.name, cb.failureCount)
}

// transitionToOpen transitions circuit breaker to OPEN state
func (cb *CircuitBreaker) transitionToOpen() {
	oldState := cb.state
	cb.state = StateOpen
	nextAttempt := time.Now().Add(cb.config.RecoveryTimeout)
	cb.nextAttemptTime = &nextAttempt
	cb.recordStateChange(oldState, StateOpen)
	log.Printf("Circuit breaker '%s' opened. Next attempt at %v", cb.name, nextAttempt)
}

// transitionToHalfOpen transitions circuit breaker to HALF_OPEN state
func (cb *CircuitBreaker) transitionToHalfOpen() {
	oldState := cb.state
	cb.state = StateHalfOpen
	cb.successCount = 0
	cb.recordStateChange(oldState, StateHalfOpen)
	log.Printf("Circuit breaker '%s' half-opened for testing", cb.name)
}

// transitionToClosed transitions circuit breaker to CLOSED state
func (cb *CircuitBreaker) transitionToClosed() {
	oldState := cb.state
	cb.state = StateClosed
	cb.failureCount = 0
	cb.successCount = 0
	cb.nextAttemptTime = nil
	cb.recordStateChange(oldState, StateClosed)
	log.Printf("Circuit breaker '%s' closed - normal operation resumed", cb.name)
}

// recordStateChange records a state change for monitoring
func (cb *CircuitBreaker) recordStateChange(fromState, toState CircuitBreakerState) {
	change := StateChange{
		Timestamp:     time.Now(),
		FromState:     fromState.String(),
		ToState:       toState.String(),
		FailureCount:  cb.failureCount,
		TotalFailures: int(cb.totalFailures),
	}

	cb.stateChanges = append(cb.stateChanges, change)

	// Keep only last 100 state changes
	if len(cb.stateChanges) > 100 {
		cb.stateChanges = cb.stateChanges[len(cb.stateChanges)-100:]
	}
}

// GetMetrics returns current circuit breaker metrics
func (cb *CircuitBreaker) GetMetrics() *Metrics {
	cb.mutex.RLock()
	defer cb.mutex.RUnlock()

	var failureRate float64
	if cb.totalRequests > 0 {
		failureRate = float64(cb.totalFailures) / float64(cb.totalRequests) * 100
	}

	// Get recent state changes (last 10)
	recentChanges := make([]StateChange, 0)
	if len(cb.stateChanges) > 0 {
		start := len(cb.stateChanges) - 10
		if start < 0 {
			start = 0
		}
		recentChanges = cb.stateChanges[start:]
	}

	return &Metrics{
		Name:               cb.name,
		State:              cb.state.String(),
		FailureCount:       cb.failureCount,
		SuccessCount:       cb.successCount,
		TotalRequests:      cb.totalRequests,
		TotalFailures:      cb.totalFailures,
		TotalSuccesses:     cb.totalSuccesses,
		FailureRate:        failureRate,
		LastFailureTime:    cb.lastFailureTime,
		NextAttemptTime:    cb.nextAttemptTime,
		Config:             cb.config,
		RecentStateChanges: recentChanges,
	}
}

// Reset resets the circuit breaker to initial state
func (cb *CircuitBreaker) Reset() {
	cb.mutex.Lock()
	defer cb.mutex.Unlock()

	cb.state = StateClosed
	cb.failureCount = 0
	cb.successCount = 0
	cb.lastFailureTime = nil
	cb.nextAttemptTime = nil
	log.Printf("Circuit breaker '%s' reset to initial state", cb.name)
}

// GetState returns the current state of the circuit breaker
func (cb *CircuitBreaker) GetState() CircuitBreakerState {
	cb.mutex.RLock()
	defer cb.mutex.RUnlock()
	return cb.state
}

// IsOpen returns true if the circuit breaker is open
func (cb *CircuitBreaker) IsOpen() bool {
	return cb.GetState() == StateOpen
}

// FallbackHandler provides fallback mechanisms when operations fail
type FallbackHandler struct {
	cache map[string]CacheEntry
	mutex sync.RWMutex
}

// CacheEntry represents a cached entry with expiration
type CacheEntry struct {
	Data      interface{}
	ExpiresAt time.Time
}

// NewFallbackHandler creates a new fallback handler
func NewFallbackHandler() *FallbackHandler {
	return &FallbackHandler{
		cache: make(map[string]CacheEntry),
	}
}

// GetFallbackRecommendations returns fallback recommendation data
func (fh *FallbackHandler) GetFallbackRecommendations() []OrigamiRecommendation {
	log.Println("Returning fallback recommendation data")
	
	return []OrigamiRecommendation{
		{
			ID:          "fallback-1",
			Name:        "Paper Crane",
			Description: "Classic origami crane - symbol of peace and hope",
			ImageURL:    "/static/images/origami/007-dove.png",
			Score:       0.95,
			Reason:      "Popular beginner choice",
		},
		{
			ID:          "fallback-2",
			Name:        "Paper Butterfly",
			Description: "Beautiful butterfly design for beginners",
			ImageURL:    "/static/images/origami/008-butterfly.png",
			Score:       0.90,
			Reason:      "Colorful and engaging",
		},
		{
			ID:          "fallback-3",
			Name:        "Paper Elephant",
			Description: "Cute elephant design with simple folds",
			ImageURL:    "/static/images/origami/004-elephant.png",
			Score:       0.85,
			Reason:      "Fun animal design",
		},
	}
}

// GetFallbackOrigamiOfTheDay returns fallback origami of the day
func (fh *FallbackHandler) GetFallbackOrigamiOfTheDay() OrigamiRecommendation {
	recommendations := fh.GetFallbackRecommendations()
	if len(recommendations) > 0 {
		return recommendations[0] // Return first as default
	}
	
	return OrigamiRecommendation{
		ID:          "default",
		Name:        "Simple Paper Fold",
		Description: "Basic origami for beginners",
		ImageURL:    "/static/images/origami/001-origami.png",
		Score:       0.80,
		Reason:      "Default recommendation",
	}
}

// CacheSuccessfulResponse caches a successful response for fallback use
func (fh *FallbackHandler) CacheSuccessfulResponse(key string, data interface{}, ttl time.Duration) {
	fh.mutex.Lock()
	defer fh.mutex.Unlock()

	fh.cache[key] = CacheEntry{
		Data:      data,
		ExpiresAt: time.Now().Add(ttl),
	}

	// Clean expired entries
	fh.cleanExpiredCache()
}

// GetCachedResponse retrieves a cached response if available and not expired
func (fh *FallbackHandler) GetCachedResponse(key string) (interface{}, bool) {
	fh.mutex.RLock()
	defer fh.mutex.RUnlock()

	entry, exists := fh.cache[key]
	if !exists {
		return nil, false
	}

	if time.Now().After(entry.ExpiresAt) {
		delete(fh.cache, key)
		return nil, false
	}

	return entry.Data, true
}

// cleanExpiredCache removes expired cache entries
func (fh *FallbackHandler) cleanExpiredCache() {
	now := time.Now()
	for key, entry := range fh.cache {
		if now.After(entry.ExpiresAt) {
			delete(fh.cache, key)
		}
	}
}

// Global instances
var (
	circuitBreakers = make(map[string]*CircuitBreaker)
	fallbackHandler = NewFallbackHandler()
	cbMutex         sync.RWMutex
)

// GetCircuitBreaker gets or creates a circuit breaker instance
func GetCircuitBreaker(name string, config *CircuitBreakerConfig) *CircuitBreaker {
	cbMutex.Lock()
	defer cbMutex.Unlock()

	if cb, exists := circuitBreakers[name]; exists {
		return cb
	}

	cb := NewCircuitBreaker(name, config)
	circuitBreakers[name] = cb
	return cb
}

// GetFallbackHandler returns the global fallback handler instance
func GetFallbackHandler() *FallbackHandler {
	return fallbackHandler
}

// GetAllCircuitBreakerMetrics returns metrics for all circuit breakers
func GetAllCircuitBreakerMetrics() map[string]*Metrics {
	cbMutex.RLock()
	defer cbMutex.RUnlock()

	metrics := make(map[string]*Metrics)
	for name, cb := range circuitBreakers {
		metrics[name] = cb.GetMetrics()
	}
	return metrics
}