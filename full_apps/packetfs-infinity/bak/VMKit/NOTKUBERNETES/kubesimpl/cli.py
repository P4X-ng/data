#!/usr/bin/env python3
"""
KubeSimpl CLI - Command-line interface for Kubernetes simplification.
"""
import argparse
import sys
from pathlib import Path
from .transformer import KubeSimplTransformer

def create_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="kubesimpl",
        description="Simplify Kubernetes manifests bidirectionally"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Expand command
    expand_parser = subparsers.add_parser(
        "expand", 
        help="Expand simplified manifest to full Kubernetes YAML"
    )
    expand_parser.add_argument("input", help="Input simplified YAML file")
    expand_parser.add_argument("output", help="Output Kubernetes YAML file")
    expand_parser.add_argument("--spec", default="specs/simplification.json", 
                              help="Simplification specification file")
    
    # Simplify command  
    simplify_parser = subparsers.add_parser(
        "simplify",
        help="Simplify full Kubernetes manifest to minimal format"
    )
    simplify_parser.add_argument("input", help="Input Kubernetes YAML file")
    simplify_parser.add_argument("output", help="Output simplified YAML file")
    simplify_parser.add_argument("--spec", default="specs/simplification.json",
                                help="Simplification specification file")
    
    # Validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate round-trip transformation fidelity"
    )
    validate_parser.add_argument("input", help="Input Kubernetes YAML file")
    validate_parser.add_argument("--spec", default="specs/simplification.json",
                                help="Simplification specification file")
    
    # Batch command
    batch_parser = subparsers.add_parser(
        "batch",
        help="Transform all files in a directory"
    )
    batch_parser.add_argument("input_dir", help="Input directory")
    batch_parser.add_argument("output_dir", help="Output directory")
    batch_parser.add_argument("direction", choices=["expand", "simplify"],
                             help="Transformation direction")
    batch_parser.add_argument("--spec", default="specs/simplification.json",
                             help="Simplification specification file")
    
    return parser

def expand_command(args) -> int:
    """Handle expand command."""
    try:
        transformer = KubeSimplTransformer(args.spec)
        transformer.transform_file(args.input, args.output, "expand")
        print(f"✅ Expanded {args.input} → {args.output}")
        return 0
    except Exception as e:
        print(f"❌ Error expanding {args.input}: {e}", file=sys.stderr)
        return 1

def simplify_command(args) -> int:
    """Handle simplify command."""
    try:
        transformer = KubeSimplTransformer(args.spec)
        transformer.transform_file(args.input, args.output, "simplify")
        print(f"✅ Simplified {args.input} → {args.output}")
        return 0
    except Exception as e:
        print(f"❌ Error simplifying {args.input}: {e}", file=sys.stderr)
        return 1

def validate_command(args) -> int:
    """Handle validate command."""
    try:
        transformer = KubeSimplTransformer(args.spec)
        
        # Load and validate file
        import yaml
        with open(args.input, 'r') as f:
            documents = list(yaml.safe_load_all(f))
        
        all_valid = True
        for i, doc in enumerate(documents):
            if doc is None:
                continue
                
            is_valid, diffs = transformer.validate_round_trip(doc)
            
            if is_valid:
                print(f"✅ Document {i+1}: Round-trip validation passed")
            else:
                print(f"❌ Document {i+1}: Round-trip validation failed")
                for field, diff in diffs.items():
                    print(f"   {field}: {diff}")
                all_valid = False
        
        return 0 if all_valid else 1
        
    except Exception as e:
        print(f"❌ Error validating {args.input}: {e}", file=sys.stderr)
        return 1

def batch_command(args) -> int:
    """Handle batch transformation."""
    try:
        transformer = KubeSimplTransformer(args.spec)
        
        input_dir = Path(args.input_dir)
        output_dir = Path(args.output_dir)
        
        if not input_dir.exists():
            print(f"❌ Input directory not found: {input_dir}", file=sys.stderr)
            return 1
        
        # Find all YAML files
        yaml_files = []
        for ext in ["*.yaml", "*.yml"]:
            yaml_files.extend(input_dir.rglob(ext))
        
        if not yaml_files:
            print(f"❌ No YAML files found in {input_dir}", file=sys.stderr)
            return 1
        
        success_count = 0
        for yaml_file in yaml_files:
            try:
                # Maintain directory structure
                relative_path = yaml_file.relative_to(input_dir)
                output_file = output_dir / relative_path
                
                transformer.transform_file(str(yaml_file), str(output_file), args.direction)
                success_count += 1
                
            except Exception as e:
                print(f"❌ Failed to transform {yaml_file}: {e}", file=sys.stderr)
        
        print(f"✅ Transformed {success_count}/{len(yaml_files)} files")
        return 0 if success_count == len(yaml_files) else 1
        
    except Exception as e:
        print(f"❌ Batch transformation error: {e}", file=sys.stderr)
        return 1

def main() -> int:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Route to appropriate command handler
    handlers = {
        "expand": expand_command,
        "simplify": simplify_command, 
        "validate": validate_command,
        "batch": batch_command
    }
    
    handler = handlers.get(args.command)
    if handler:
        return handler(args)
    else:
        print(f"❌ Unknown command: {args.command}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
