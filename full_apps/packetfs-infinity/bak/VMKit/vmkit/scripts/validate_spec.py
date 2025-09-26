#!/usr/bin/env python3
"""
Validate simplification specification against schema and business rules.
"""
import json
import jsonschema
from pathlib import Path
from typing import Dict, Any, List, Tuple

def load_schema() -> Dict[str, Any]:
    """Load the JSON schema."""
    schema_path = Path("schemas/simplification-spec.schema.json")
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")
    
    with open(schema_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_specification() -> Dict[str, Any]:
    """Load the specification file."""
    spec_path = Path("specs/simplification.json")
    if not spec_path.exists():
        raise FileNotFoundError(f"Specification not found: {spec_path}")
    
    with open(spec_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def validate_against_schema(spec: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    """Validate specification against JSON Schema."""
    errors = []
    
    try:
        jsonschema.validate(spec, schema)
        print("✓ Schema validation passed")
    except jsonschema.ValidationError as e:
        errors.append(f"Schema validation failed: {e.message}")
        if e.path:
            errors.append(f"  Path: {' -> '.join(str(p) for p in e.path)}")
    except jsonschema.SchemaError as e:
        errors.append(f"Schema error: {e.message}")
    
    return errors

def validate_business_rules(spec: Dict[str, Any]) -> List[str]:
    """Validate business logic and invariants."""
    errors = []
    
    # Check for unknown top-level keys
    expected_keys = {
        "specVersion", "metadata", "vocabulary", "resources", "fields", 
        "defaults", "validations", "transforms", "constraints", "presets",
        "examples", "removals", "replacements", "access_control", 
        "networking", "deployment", "container_runtime", "simplified_resources",
        "job_system", "configuration", "performance", "kubectl_integration"
    }
    
    unknown_keys = set(spec.keys()) - expected_keys
    if unknown_keys:
        errors.append(f"Unknown top-level keys: {sorted(unknown_keys)}")
    
    # Check for unused presets
    presets = spec.get("presets", {})
    examples = spec.get("examples", [])
    
    preset_usage = set()
    for example in examples:
        if "preset" in example.get("input", {}):
            preset_usage.add(example["input"]["preset"])
    
    unused_presets = set(presets.keys()) - preset_usage
    if unused_presets:
        errors.append(f"Unused presets: {sorted(unused_presets)}")
    
    # Check for conflicting defaults
    defaults = spec.get("defaults", {})
    fields = spec.get("fields", {})
    
    for field_path, field_spec in fields.items():
        field_default = field_spec.get("default")
        global_default = defaults.get(field_path)
        
        if field_default is not None and global_default is not None:
            if field_default != global_default:
                errors.append(f"Conflicting defaults for {field_path}: field={field_default}, global={global_default}")
    
    # Check referential integrity in transforms
    transforms = spec.get("transforms", {})
    
    # Validate rename mappings reference valid fields
    rename_mappings = transforms.get("rename", {})
    for old_field, new_field in rename_mappings.items():
        if old_field in fields and new_field not in fields:
            # This is expected - we're renaming from complex to simple
            pass
    
    # Validate computed fields reference available data
    compute_mappings = transforms.get("compute", {})
    for field, expression in compute_mappings.items():
        if "${metadata.name}" in expression and "metadata.name" not in fields:
            errors.append(f"Computed field {field} references unavailable metadata.name")
    
    # Validate constraints reference valid fields
    constraints = spec.get("constraints", [])
    for constraint in constraints:
        condition = constraint.get("condition", "")
        # Basic check for field references
        if "metadata.name" in condition and "metadata.name" not in fields:
            errors.append(f"Constraint '{constraint.get('name')}' references unavailable metadata.name")
    
    if not errors:
        print("✓ Business rules validation passed")
    
    return errors

def validate_specification() -> Tuple[bool, List[str]]:
    """Main validation function."""
    try:
        # Load schema and specification
        schema = load_schema()
        spec = load_specification()
        
        print("Validating specification...")
        
        # Run validations
        schema_errors = validate_against_schema(spec, schema)
        business_errors = validate_business_rules(spec)
        
        all_errors = schema_errors + business_errors
        
        if not all_errors:
            print("✅ All validations passed!")
            return True, []
        else:
            print(f"❌ Validation failed with {len(all_errors)} error(s):")
            for error in all_errors:
                print(f"  - {error}")
            return False, all_errors
            
    except FileNotFoundError as e:
        error_msg = f"File not found: {e}"
        print(f"❌ {error_msg}")
        return False, [error_msg]
    except json.JSONDecodeError as e:
        error_msg = f"JSON parsing error: {e}"
        print(f"❌ {error_msg}")
        return False, [error_msg]
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        print(f"❌ {error_msg}")
        return False, [error_msg]

if __name__ == "__main__":
    import sys
    
    success, errors = validate_specification()
    if not success:
        sys.exit(1)
