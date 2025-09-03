#!/usr/bin/env python3
"""
VMKit Cleanup Script
Organizes and validates the codebase
"""

import os
import sys
from pathlib import Path
import subprocess

def check_python_syntax():
    """Check Python syntax for all modules"""
    print("Checking Python syntax...")
    vmkit_dir = Path(__file__).parent / "vmkit"
    
    for py_file in vmkit_dir.glob("*.py"):
        try:
            with open(py_file) as f:
                compile(f.read(), py_file, 'exec')
            print(f"✓ {py_file.name}")
        except SyntaxError as e:
            print(f"✗ {py_file.name}: {e}")
            return False
    return True

def check_imports():
    """Check for import issues"""
    print("\nChecking imports...")
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        import vmkit
        print("✓ VMKit imports successfully")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def organize_files():
    """Organize project files"""
    print("\nOrganizing files...")
    
    # Create directories if they don't exist
    dirs = ['docs', 'tests', 'examples', 'scripts']
    for dir_name in dirs:
        dir_path = Path(__file__).parent / dir_name
        dir_path.mkdir(exist_ok=True)
        print(f"✓ Created/verified {dir_name}/ directory")

def main():
    """Main cleanup function"""
    print("VMKit Cleanup Script")
    print("=" * 40)
    
    success = True
    success &= check_python_syntax()
    success &= check_imports()
    organize_files()
    
    if success:
        print("\n✅ Cleanup completed successfully!")
        print("\nNext steps:")
        print("1. Run tests: python -m pytest tests/")
        print("2. Install: pip install -e .")
        print("3. Try CLI: vmkit --help")
    else:
        print("\n❌ Cleanup found issues that need fixing")
        sys.exit(1)

if __name__ == "__main__":
    main()