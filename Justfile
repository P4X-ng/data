# PacketFS root orchestrator (single-target steps, no inline chaining)

VENV_PATH := "/home/punk/.venv"

# Standard targets

setup:
    @echo "Setting up PacketFS dev environment"
    {{VENV_PATH}}/bin/pip install -q -U pip setuptools wheel
    @echo "Done"

build:
    @echo "Build: compile native extensions if packaging is configured"
    @echo "(skipping: provide setup.py/pyproject to enable)"

test:
    @echo "Running tests"
    PYTHONPATH=realsrc {{VENV_PATH}}/bin/python -m pytest -q dev/working/tests

lint:
    @echo "Linting"
    {{VENV_PATH}}/bin/black --check realsrc dev/working/tools
    {{VENV_PATH}}/bin/flake8 realsrc dev/working/tools

format:
    @echo "Formatting"
    {{VENV_PATH}}/bin/black realsrc dev/working/tools

bench:
    @echo "Benchmarks"
    {{VENV_PATH}}/bin/python dev/working/tools/perf_benchmark.py

clean:
    @echo "Cleaning work artifacts"
    find . -name "__pycache__" -type d -prune -exec rm -rf {} +
    find . -name "*.pyc" -delete

