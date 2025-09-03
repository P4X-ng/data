.PHONY: help install test compare analyze clean setup
.DEFAULT_GOAL := help

VENV_PATH := /home/punk/.venv
PYTHON := $(VENV_PATH)/bin/python
PIP := $(VENV_PATH)/bin/pip
REMOTE_HOST := 10.69.69.235

help: ## Show this help message
	@echo "PacketFS - Ultimate Performance Comparison Suite"
	@echo "=============================================="
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Examples:"
	@echo "  make setup          # Initial setup and environment preparation"
	@echo "  make compare        # Run ultimate comparison with default sizes (10, 50, 100 MB)"
	@echo "  make compare-large  # Run comparison with large files (100, 500, 1000 MB)"
	@echo "  make test           # Run unit and integration tests"
	@echo "  make analyze        # Generate analysis reports from existing results"
	@echo ""

setup: ## Setup development environment and dependencies
	@echo "🚀 Setting up PacketFS development environment..."
	@source $(VENV_PATH)/bin/activate && pip install -r requirements.txt
	@$(PYTHON) setup.py develop
	@echo "✅ Setup completed!"

install: setup ## Alias for setup

test: ## Run unit tests, integration tests, and performance benchmarks
	@echo "🧪 Running comprehensive test suite..."
	@source $(VENV_PATH)/bin/activate && pytest tests/ -v
	@$(PYTHON) tools/perf_benchmark.py
	@$(PYTHON) tools/simple_packetfs_test.py
	@echo "✅ All tests completed!"

compare: ## Run ultimate comparison test (default sizes: 10, 50, 100 MB)
	@echo "🏆 Running ultimate PacketFS vs TCP comparison..."
	@mkdir -p results/$(shell date +%Y%m%d_%H%M%S)
	@$(PYTHON) tools/ultimate_comparison_test.py compare \
		--sizes 10 50 100 \
		--remote $(REMOTE_HOST) \
		| tee results/$(shell date +%Y%m%d_%H%M%S)/comparison.log
	@echo "✅ Ultimate comparison completed!"

compare-large: ## Run comparison with large files (100, 500, 1000 MB)
	@echo "🏆 Running large file comparison test..."
	@mkdir -p results/$(shell date +%Y%m%d_%H%M%S)
	@$(PYTHON) tools/ultimate_comparison_test.py compare \
		--sizes 100 500 1000 \
		--remote $(REMOTE_HOST) \
		| tee results/$(shell date +%Y%m%d_%H%M%S)/large_comparison.log
	@echo "✅ Large file comparison completed!"

compare-small: ## Run comparison with small files (1, 5, 10 MB)
	@echo "🏆 Running small file comparison test..."
	@mkdir -p results/$(shell date +%Y%m%d_%H%M%S)
	@$(PYTHON) tools/ultimate_comparison_test.py compare \
		--sizes 1 5 10 \
		--remote $(REMOTE_HOST) \
		| tee results/$(shell date +%Y%m%d_%H%M%S)/small_comparison.log
	@echo "✅ Small file comparison completed!"

analyze: ## Generate analysis reports from existing test results
	@echo "📊 Generating analysis reports..."
	@$(PYTHON) tools/analyze_test_results.py
	@echo "✅ Analysis completed!"

network-sim: ## Run network simulation tests (requires root)
	@echo "🌐 Running network simulation tests..."
	@sudo $(PYTHON) tools/test_network_simulation.py
	@echo "✅ Network simulation completed!"

deploy-test: ## Deploy and test on remote machine
	@echo "🚀 Deploying and testing on remote machine..."
	@$(PYTHON) tools/deploy_network_tests.py
	@echo "✅ Remote deployment test completed!"

benchmark: ## Run performance benchmarks only
	@echo "⚡ Running performance benchmarks..."
	@$(PYTHON) tools/perf_benchmark.py
	@$(PYTHON) tools/simple_packetfs_test.py
	@echo "✅ Benchmarks completed!"

lint: ## Run code linting and formatting
	@echo "🔍 Running code linting..."
	@source $(VENV_PATH)/bin/activate && python -m black tools/ src/ tests/
	@source $(VENV_PATH)/bin/activate && python -m flake8 tools/ src/ tests/
	@echo "✅ Linting completed!"

clean: ## Clean up generated files and results
	@echo "🧹 Cleaning up..."
	@rm -rf build/ dist/ *.egg-info/
	@rm -rf .pytest_cache/
	@rm -rf __pycache__/ */__pycache__/ */*/__pycache__/
	@rm -f *.pyc */*.pyc */*/*.pyc
	@rm -f test_file_*.bin received_*.bin
	@rm -f *.log
	@echo "✅ Cleanup completed!"

clean-results: ## Clean up test results and logs
	@echo "🧹 Cleaning up test results..."
	@rm -rf results/
	@rm -rf logs/
	@rm -f *_results.json
	@rm -f *.log
	@echo "✅ Results cleanup completed!"

check-remote: ## Check remote connectivity and PacketFS service
	@echo "🔍 Checking remote connectivity..."
	@ping -c 3 $(REMOTE_HOST)
	@ssh punk@$(REMOTE_HOST) "echo 'SSH connection successful'"
	@ssh punk@$(REMOTE_HOST) "cd ~/packetfs-remote && ls -la"
	@echo "✅ Remote check completed!"

sync-remote: ## Sync code to remote machine
	@echo "🔄 Syncing code to remote machine..."
	@rsync -avz --exclude='.git' --exclude='__pycache__' \
		--exclude='*.pyc' --exclude='logs/' --exclude='results/' \
		. punk@$(REMOTE_HOST):~/packetfs-remote/
	@echo "✅ Code sync completed!"

all: setup test compare analyze ## Run complete test suite (setup, test, compare, analyze)
	@echo "🎉 Complete test suite finished!"

status: ## Show current project status
	@echo "PacketFS Project Status"
	@echo "======================="
	@echo "Python environment: $(PYTHON)"
	@echo "Remote host: $(REMOTE_HOST)"
	@echo "Git branch: $(shell git branch --show-current)"
	@echo "Git status: $(shell git status --porcelain | wc -l) modified files"
	@echo "Recent results:"
	@ls -la results/ 2>/dev/null | tail -5 || echo "No results found"
	@echo "Recent logs:"
	@ls -la logs/ 2>/dev/null | tail -5 || echo "No logs found"
