#!/usr/bin/env python3
"""
Build script for KubeSimpl CLI and library.
"""
import os
import sys
from pathlib import Path
import subprocess

def create_executable():
    """Create executable CLI script."""
    cli_script = """#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kubesimpl.cli import main

if __name__ == "__main__":
    sys.exit(main())
"""
    
    # Create bin directory and script
    bin_dir = Path("bin")
    bin_dir.mkdir(exist_ok=True)
    
    cli_path = bin_dir / "kubesimpl"
    with open(cli_path, 'w', encoding='utf-8') as f:
        f.write(cli_script)
    
    # Make executable
    os.chmod(cli_path, 0o755)
    
    print(f"✅ Created executable: {cli_path}")

def install_dependencies():
    """Install required Python dependencies.

    Strategy:
    - Prefer system packages where available (using correct Debian/Ubuntu package names)
    - Fallback to the central venv pip at /home/punk/.venv/bin/pip per project rules
    """
    dependencies = [
        "pyyaml",
        "jsonschema"
    ]

    # Map Python package names to apt package suffixes
    # Ubuntu/Debian: PyYAML is provided as python3-yaml (not python3-pyyaml)
    apt_name_map = {
        "pyyaml": "yaml",
        "jsonschema": "jsonschema",
    }

    pip_path = Path("/home/punk/.venv/bin/pip")

    print("Installing dependencies...")

    for dep in dependencies:
        apt_pkg = f"python3-{apt_name_map.get(dep, dep).replace('_', '-')}"
        try:
            # Try installing via apt first
            result = subprocess.run(
                ["sudo", "apt-get", "install", "-y", apt_pkg],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                print(f"✅ Installed {dep} (via {apt_pkg})")
                continue
            else:
                print(f"❌ Apt install failed for {dep} ({apt_pkg}): {result.stderr.strip()}")

            # Fallback to pip in the central venv
            if pip_path.exists():
                pip_result = subprocess.run(
                    [str(pip_path), "install", dep],
                    capture_output=True,
                    text=True,
                )
                if pip_result.returncode == 0:
                    print(f"✅ Installed {dep} (via {pip_path})")
                else:
                    print(f"❌ Pip install failed for {dep}: {pip_result.stderr.strip()}")
            else:
                print(
                    "❌ Central venv pip not found at /home/punk/.venv/bin/pip; "
                    f"please create it or install '{dep}' manually"
                )
        except Exception as e:
            print(f"❌ Error installing {dep}: {e}")

def validate_build():
    """Validate that the build was successful."""
    print("Validating build...")

    # Resolve project root relative to this script (.../NOTKUBERNETES)
    project_root = Path(__file__).resolve().parent.parent
    
    # Check that CLI is executable
    cli_path = Path("bin/kubesimpl")
    if not cli_path.exists():
        print("❌ CLI script not found")
        return False
    
    if not os.access(cli_path, os.X_OK):
        print("❌ CLI script not executable")
        return False
    
    # Check that modules can be imported
    try:
        import sys
        # Ensure we can import the local package regardless of CWD
        sys.path.insert(0, str(project_root))
        from kubesimpl import KubeSimplTransformer
        print("✅ KubeSimplTransformer can be imported")
    except ImportError as e:
        print(f"❌ Cannot import KubeSimplTransformer: {e}")
        return False
    
    # Check spec file exists (relative to project root)
    spec_path = project_root / "specs/simplification.json"
    if not spec_path.exists():
        print("❌ Specification file not found")
        return False
    
    print("✅ Build validation passed")
    return True

def main():
    """Main build function."""
    print("Building KubeSimpl CLI and library...")
    
    # Install dependencies
    install_dependencies()
    
    # Create executable
    create_executable()
    
    # Validate build
    if validate_build():
        print("🚀 Build completed successfully!")
        print("Usage: ./bin/kubesimpl --help")
        return 0
    else:
        print("❌ Build validation failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
