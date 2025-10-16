# Makefile for Recommendation Service

.PHONY: test test-unit test-integration test-performance coverage coverage-html benchmark clean help

# Go parameters
GOCMD=go
GOBUILD=$(GOCMD) build
GOCLEAN=$(GOCMD) clean
GOTEST=$(GOCMD) test
GOGET=$(GOCMD) get
GOMOD=$(GOCMD) mod
BINARY_NAME=recommendation
COVERAGE_FILE=coverage.out
INTEGRATION_COVERAGE_FILE=integration_coverage.out
BENCHMARK_FILE=benchmark.txt

# Test parameters
TEST_TIMEOUT=30s
COVERAGE_THRESHOLD=80

help: ## Display this help message
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

deps: ## Download dependencies
	$(GOMOD) download
	$(GOMOD) tidy

test: test-unit test-integration ## Run all tests

test-unit: ## Run unit tests with coverage
	@echo "Running unit tests..."
	$(GOTEST) -v -race -timeout $(TEST_TIMEOUT) \
		-coverprofile=$(COVERAGE_FILE) \
		-covermode=atomic \
		./... \
		-tags="!integration"

test-integration: ## Run integration tests
	@echo "Running integration tests..."
	$(GOTEST) -v -race -timeout $(TEST_TIMEOUT) \
		-coverprofile=$(INTEGRATION_COVERAGE_FILE) \
		-covermode=atomic \
		./tests/ \
		-tags=integration

test-performance: ## Run performance tests
	@echo "Running performance tests..."
	$(GOTEST) -v -bench=. -benchmem -run=^$$ ./tests/ > $(BENCHMARK_FILE) 2>&1 || true

coverage: test-unit ## Generate coverage report
	@echo "Generating coverage report..."
	$(GOCMD) tool cover -func=$(COVERAGE_FILE)
	@echo ""
	@echo "Coverage threshold check ($(COVERAGE_THRESHOLD)%):"
	@COVERAGE=$$($(GOCMD) tool cover -func=$(COVERAGE_FILE) | grep total | awk '{print $$3}' | sed 's/%//'); \
	if [ $$(echo "$$COVERAGE >= $(COVERAGE_THRESHOLD)" | bc -l) -eq 1 ]; then \
		echo "✅ Coverage ($$COVERAGE%) meets threshold ($(COVERAGE_THRESHOLD)%)"; \
	else \
		echo "❌ Coverage ($$COVERAGE%) below threshold ($(COVERAGE_THRESHOLD)%)"; \
		exit 1; \
	fi

coverage-html: test-unit ## Generate HTML coverage report
	@echo "Generating HTML coverage report..."
	$(GOCMD) tool cover -html=$(COVERAGE_FILE) -o coverage.html
	@echo "Coverage report generated: coverage.html"

coverage-xml: test-unit ## Generate XML coverage report (for CI)
	@echo "Generating XML coverage report..."
	@command -v gocov >/dev/null 2>&1 || { echo "Installing gocov..."; $(GOGET) github.com/axw/gocov/gocov; }
	@command -v gocov-xml >/dev/null 2>&1 || { echo "Installing gocov-xml..."; $(GOGET) github.com/AlekSi/gocov-xml; }
	gocov convert $(COVERAGE_FILE) | gocov-xml > coverage.xml

benchmark: test-performance ## Run benchmarks and display results
	@echo "Benchmark results:"
	@cat $(BENCHMARK_FILE) 2>/dev/null || echo "No benchmark results found. Run 'make test-performance' first."

quality-check: coverage ## Run quality checks
	@echo "Running quality checks..."
	@echo "1. Coverage check: ✅"
	@echo "2. Race condition check: ✅"
	@echo "3. Vet check:"
	$(GOCMD) vet ./...
	@echo "4. Format check:"
	@if [ -n "$$(gofmt -l .)" ]; then \
		echo "❌ Code not formatted. Run 'gofmt -w .'"; \
		exit 1; \
	else \
		echo "✅ Code properly formatted"; \
	fi

build: ## Build the binary
	$(GOBUILD) -o $(BINARY_NAME) -v ./...

clean: ## Clean build artifacts and test files
	$(GOCLEAN)
	rm -f $(BINARY_NAME)
	rm -f $(COVERAGE_FILE)
	rm -f $(INTEGRATION_COVERAGE_FILE)
	rm -f coverage.html
	rm -f coverage.xml
	rm -f $(BENCHMARK_FILE)

ci-test: deps test coverage-xml benchmark ## Run all tests for CI pipeline
	@echo "CI test suite completed successfully"

# Development helpers
dev-setup: deps ## Setup development environment
	@echo "Setting up development environment..."
	$(GOGET) github.com/axw/gocov/gocov
	$(GOGET) github.com/AlekSi/gocov-xml
	$(GOGET) github.com/jstemmer/go-junit-report/v2@latest
	@echo "Development environment ready"

watch-test: ## Watch for changes and run tests
	@echo "Watching for changes... (Press Ctrl+C to stop)"
	@while true; do \
		$(GOTEST) -v ./... || true; \
		inotifywait -qre modify . --exclude='\.git|coverage\.|\.out$$|\.html$$'; \
	done

# Docker helpers
docker-test: ## Run tests in Docker container
	docker run --rm -v $(PWD):/app -w /app golang:1.21-alpine sh -c "apk add --no-cache make && make ci-test"

.DEFAULT_GOAL := help