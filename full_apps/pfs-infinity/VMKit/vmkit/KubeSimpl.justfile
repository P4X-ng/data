# KubeSimpl - Simplified Kubernetes Implementation

# Default recipe displays available targets
default:
    @just --list

# Environment setup - use central venv, create placeholders
setup:
    python3 -m venv /home/punk/.venv --upgrade-deps || echo "Using existing venv"
    mkdir -p input schemas specs examples/input examples/output
    touch AUTOMATION.txt
    echo "[WARP.md missing – add strategic context]" > WARP.md || true
    echo "[PROJECT.txt missing – add high-level summary]" > PROJECT.txt || true
    chown -R punk:punk . || true

# Generate JSON Schema for simplification specification
gen-schema:
    python3 scripts/gen_schema.py

# Parse requirements into normalized spec format
parse-reqs:
    python3 scripts/parse_requirements.py

# Validate spec against schema and business rules
validate-spec:
    python3 scripts/validate_spec.py

# Build CLI and transformer library
build:
    python3 -m build

# Run sample transformations end-to-end
run:
    python3 scripts/run_transforms.py

# Execute unit and integration tests
test:
    python3 -m pytest tests/ -v

# Static analysis and linting
lint:
    python3 -m ruff check .
    python3 -m yamllint schemas/ specs/ examples/

# Format code and documentation
format:
    python3 -m black .
    python3 -m ruff format .

# Generate documentation
docs:
    python3 scripts/gen_docs.py

# Regenerate copilot instructions
regen-copilot:
    python3 scripts/regen_copilot.py

# Package and deploy
deploy:
    python3 scripts/deploy.py

# Performance benchmarking
bench:
    python3 scripts/benchmark.py

# Clean build artifacts
clean:
    rm -rf build/ dist/ __pycache__/ .pytest_cache/
    find . -name "*.pyc" -delete
