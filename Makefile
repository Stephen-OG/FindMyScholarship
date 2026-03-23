# ===============================
# 🧠 FindMyScholarship Makefile
# Simplifies development workflow with uv + OpenAI + Gradio
# ===============================

# Environment
UV_RUN = uv run --active
PYTHON = $(UV_RUN) python
GRADIO = $(UV_RUN) gradio
VENV = .venv
APP = app.py

# Default target
.DEFAULT_GOAL := help

# -------------------------------
# 🔧 Setup
# -------------------------------

install: 
	@echo "🔧installing dependencies."
	python3 -m venv .venv
	source .venv/bin/activate && pip install -r requirements.txt
	
setup:	## Create virtual environment and install dependencies
	@echo "🔧 Setting up environment..."
	uv sync

update: ## Update dependencies from pyproject.toml
	@echo "⬆️  Updating environment..."
	uv lock --upgrade
	uv sync

clean: ## Remove all build, cache, and venv files
	@echo "🧹 Cleaning up..."
	rm -rf __pycache__/ .pytest_cache/ .ruff_cache/ .mypy_cache/ $(VENV)

# -------------------------------
# 🚀 Run App
# -------------------------------

run: ## Run main app
	@echo "🚀 Starting FindMyScholarship..."
	$(PYTHON) $(APP)

dev: ## Start development mode (auto-reload + lint check)
	@echo "🔧 Fixing lintable issues with Ruff..."
	$(UV_RUN) ruff check . --fix || true
	@echo "🖋️ Formatting code with Ruff..."
	$(UV_RUN) ruff format . || true
	@echo "🚀 Launching Gradio in development mode with auto-reload..."
	$(UV_RUN) gradio $(APP)

gradio: ## Launch Gradio app interface
	@echo "🌐 Launching Gradio UI..."
	$(GRADIO) $(APP)

shell: ## Enter uv-managed shell
	@uv shell

# -------------------------------
# 🧪 Testing and Linting
# -------------------------------

test: ## Run pytest suite
	@echo "🧪 Running tests..."
	$(UV_RUN) pytest -v

lint: ## Run Ruff linter and auto-fix
	@echo "✨ Linting with Ruff..."
	$(UV_RUN) ruff check --fix .

format: ## Format code with Black
	@echo "🖋️  Formatting with Ruff..."
	$(UV_RUN) ruff format .

check: lint format ## Run linting and formatting together

# -------------------------------
# 🧭 Utility
# -------------------------------

deps: ## Show installed dependencies
	@echo "📦 Installed packages:"
	uv pip list

help: ## Display help
	@echo "Usage: make [target]\n"
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
