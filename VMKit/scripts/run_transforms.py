#!/usr/bin/env python3
"""
Run sample transformations end-to-end for KubeSimpl.
"""
import os
import sys
from pathlib import Path
import subprocess
import yaml

def run_transformation_demo():
    """Run demonstration of transformations."""
    print("🚀 KubeSimpl Transformation Demo")
    print("=" * 50)
    
    # Ensure output directory exists
    output_dir = Path("examples/output")
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # Test 1: Expand simplified to full Kubernetes
    print("\n📤 Test 1: Expand simplified manifest to full Kubernetes")
    simple_file = "examples/input/simple-app.yaml"
    expanded_file = "examples/output/simple-app-expanded.yaml"
    
    if Path(simple_file).exists():
        result = subprocess.run([
            "./bin/kubesimpl", "expand", simple_file, expanded_file
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ {result.stdout.strip()}")
            print(f"   View output: {expanded_file}")
        else:
            print(f"❌ Expansion failed: {result.stderr}")
    else:
        print(f"❌ Input file not found: {simple_file}")
    
    # Test 2: Simplify full Kubernetes to minimal
    print("\n📥 Test 2: Simplify full Kubernetes manifest")
    full_file = "examples/input/web-app-example.yaml"
    simplified_file = "examples/output/web-app-simplified.yaml"
    
    if Path(full_file).exists():
        result = subprocess.run([
            "./bin/kubesimpl", "simplify", full_file, simplified_file
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ {result.stdout.strip()}")
            print(f"   View output: {simplified_file}")
        else:
            print(f"❌ Simplification failed: {result.stderr}")
    else:
        print(f"❌ Input file not found: {full_file}")
    
    # Test 3: Round-trip validation
    print("\n🔄 Test 3: Round-trip validation")
    if Path(full_file).exists():
        result = subprocess.run([
            "./bin/kubesimpl", "validate", full_file
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Round-trip validation passed")
            print(result.stdout)
        else:
            print("❌ Round-trip validation failed")
            print(result.stderr)
    
    # Test 4: Batch transformation
    print("\n📦 Test 4: Batch transformation")
    result = subprocess.run([
        "./bin/kubesimpl", "batch", "examples/input", "examples/output", "expand"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✅ {result.stdout.strip()}")
    else:
        print(f"❌ Batch transformation failed: {result.stderr}")

def show_transformation_examples():
    """Show before/after examples of transformations."""
    print("\n📋 Transformation Examples")
    print("=" * 50)
    
    # Show simplified input
    simple_file = Path("examples/input/simple-app.yaml")
    if simple_file.exists():
        print("\n📄 Simplified Input (simple-app.yaml):")
        print("-" * 40)
        print(simple_file.read_text())
    
    # Show expanded output
    expanded_file = Path("examples/output/simple-app-expanded.yaml")
    if expanded_file.exists():
        print("📄 Expanded Output (simple-app-expanded.yaml):")
        print("-" * 40)
        print(expanded_file.read_text())

def verify_round_trip_fidelity():
    """Verify round-trip transformation fidelity."""
    print("\n🔍 Round-trip Fidelity Report")
    print("=" * 50)
    
    input_dir = Path("examples/input")
    output_dir = Path("examples/output")
    
    yaml_files = list(input_dir.glob("*.yaml")) + list(input_dir.glob("*.yml"))
    
    if not yaml_files:
        print("❌ No YAML files found for testing")
        return
    
    for yaml_file in yaml_files:
        print(f"\n📄 Testing {yaml_file.name}:")
        
        # Run validation
        result = subprocess.run([
            "./bin/kubesimpl", "validate", str(yaml_file)
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"   ✅ Round-trip validation passed")
        else:
            print(f"   ❌ Round-trip validation failed")
            if result.stderr:
                print(f"      Error: {result.stderr.strip()}")

def main():
    """Main transformation demo."""
    print("KubeSimpl End-to-End Transformation Testing")
    
    # Check that CLI is built
    cli_path = Path("bin/kubesimpl")
    if not cli_path.exists():
        print("❌ CLI not found. Run 'just build' first.")
        return 1
    
    # Check that spec exists
    spec_path = Path("specs/simplification.json")
    if not spec_path.exists():
        print("❌ Specification not found. Run 'just parse-reqs' first.")
        return 1
    
    # Run transformation demo
    run_transformation_demo()
    
    # Show examples
    show_transformation_examples()
    
    # Verify fidelity
    verify_round_trip_fidelity()
    
    print("\n🎉 Transformation testing complete!")
    print("📁 Check examples/output/ for generated files")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
