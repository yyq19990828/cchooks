# cchooks Makefile - Development utilities with uv

# Project configuration
PACKAGE_NAME := cchooks
SRC_DIR := src
TEST_DIR := tests
COVERAGE_DIR := htmlcov
DIST_DIR := dist

# Default target
.PHONY: help
help: ## Show this help message
	@echo "cchooks Development Commands"
	@echo "=============================="
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "%-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Environment setup
.PHONY: setup
setup: ## Install development dependencies and setup environment
	@echo "Setting up development environment..."
	@uv sync
	@uv pip install -e ".[dev]"
	@echo "Development environment ready!"

.PHONY: lock
lock: ## Update dependency lockfile
	@echo "Updating lockfile..."
	@uv lock
	@echo "Lockfile updated!"

# Testing targets
.PHONY: test
test: ## Run the complete test suite with coverage
	@echo "Running test suite..."
	@uv run pytest $(TEST_DIR)/ -v \
		--cov=$(SRC_DIR)/$(PACKAGE_NAME) \
		--cov-report=term-missing \
		--cov-report=html \
		--cov-report=xml
	@echo "Test suite complete!"
	@echo "Coverage report: $(COVERAGE_DIR)/index.html"

.PHONY: test-quick
test-quick: ## Run tests without coverage (faster)
	@echo "Running quick tests..."
	@uv run pytest $(TEST_DIR)/ -v
	@echo "Quick tests complete!"

# Linting and formatting
.PHONY: lint
lint: ## Run linting with ruff
	@echo "Running linting..."
	@uv run ruff check $(SRC_DIR)/
	@echo "Linting complete!"

.PHONY: lint-fix
lint-fix: ## Run linting and auto-fix issues
	@echo "Running linting with auto-fix..."
	@uv run ruff check $(SRC_DIR)/ --fix
	@echo "Linting fixes applied!"

.PHONY: format
format: ## Format code with ruff
	@echo "Formatting code..."
	@uv run ruff format $(SRC_DIR)/
	@echo "Code formatted!"

.PHONY: format-check
format-check: ## Check code formatting
	@echo "Checking code formatting..."
	@uv run ruff format --check $(SRC_DIR)/
	@echo "Formatting check complete!"

# Type checking
.PHONY: type-check
type-check: ## Run type checking with mypy
	@echo "Running type checks..."
	@uv run mypy $(SRC_DIR)/
	@echo "Type checks complete!"

# Build and distribution
.PHONY: build
build: ## Build the package
	@echo "Building package..."
	@uv build
	@echo "Build complete!"
	@echo "Built files in $(DIST_DIR)/"

.PHONY: check
check: lint type-check format-check test ## Run all checks (lint, type-check, format-check, test)
	@echo "All checks passed!"

# Cleanup
.PHONY: clean
clean: ## Clean build artifacts and cache
	@echo "Cleaning up..."
	@rm -rf $(DIST_DIR)/
	@rm -rf $(COVERAGE_DIR)/
	@rm -rf .pytest_cache/
	@rm -rf .ruff_cache/
	@rm -rf .coverage
	@rm -rf coverage.xml
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete
	@echo "Cleanup complete!"

.PHONY: clean-all
clean-all: clean ## Clean everything including virtual environment
	@echo "Cleaning everything..."
	@rm -rf .venv/
	@echo "Complete cleanup!"

# Development utilities
.PHONY: install-dev
install-dev: ## Install package in development mode
	@echo "Installing in development mode..."
	@uv pip install -e ".[dev]"
	@echo "Development installation complete!"

.PHONY: deps-tree
deps-tree: ## Show dependency tree
	@echo "Dependency tree:"
	@uv tree

# Release preparation
.PHONY: release-check
release-check: check clean build ## Full release preparation check
	@echo "Release check complete! Ready to publish."
