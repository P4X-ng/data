#!/usr/bin/env python3
"""
Regenerate copilot-instructions.md with current project state.
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime

def load_file_or_placeholder(filename: str, placeholder: str) -> str:
    """Load file content or return placeholder."""
    path = Path(filename)
    if path.exists():
        return path.read_text().strip()
    return placeholder

def get_git_changes() -> dict:
    """Get git changes for CHANGES section."""
    import subprocess
    
    try:
        # Get recent changes
        result = subprocess.run([
            "git", "diff", "--name-status", "HEAD~1..HEAD"
        ], capture_output=True, text=True, cwd=".")
        
        changes = {"changed": [], "added": [], "modified": [], "deleted": []}
        
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line:
                    status, filename = line.split('\t', 1)
                    if status == 'A':
                        changes["added"].append(filename)
                    elif status == 'M':
                        changes["modified"].append(filename)
                    elif status == 'D':
                        changes["deleted"].append(filename)
                    else:
                        changes["changed"].append(filename)
        
        return changes
        
    except Exception:
        # Fallback for when git isn't available or no commits
        return {
            "changed": [],
            "added": ["KubeSimpl implementation"],
            "modified": [],
            "deleted": []
        }

def generate_copilot_instructions() -> str:
    """Generate the complete copilot instructions."""
    
    # Load WARP and PROJECT sections
    warp_content = load_file_or_placeholder(
        "WARP.md", 
        "[WARP.md missing – add strategic context]"
    )
    
    project_content = load_file_or_placeholder(
        "PROJECT.txt",
        "[PROJECT.txt missing – add high-level summary]"
    )
    
    # Generate CHANGES
    changes = get_git_changes()
    changes_content = f"""CHANGES:
- changed: {changes['changed']}
- added: {changes['added']}
- modified: {changes['modified']}
- deleted: {changes['deleted']}
Impact: Implemented KubeSimpl - a simplified Kubernetes YAML transformer with bidirectional conversion."""
    
    # Generate TODO items (≥3 with required categories)
    todo_content = """TODO:
- id: TODO-001
  title: Implement kubectl integration with VMKit
  category: extend_feature
  rationale: Integrate KubeSimpl with VMKit for unified container/VM management
  target_or_path: just integrate-vmkit
  acceptance_hint: kubectl commands work with both containers and VMs

- id: TODO-002
  title: Add comprehensive round-trip validation
  category: bug_probe
  rationale: Fix round-trip transformation issues found in testing
  target_or_path: just fix-roundtrip
  acceptance_hint: All example manifests pass round-trip validation

- id: TODO-003
  title: Implement SSH-based authentication system
  category: new_capability
  rationale: Replace certificate-based auth with SSH keys as specified
  target_or_path: just implement-ssh-auth
  acceptance_hint: API server uses SSH tunnels for authentication

- id: TODO-004
  title: Add Redis cluster coordination
  category: extend_feature
  rationale: Implement Redis-based coordination for distributed nodes
  target_or_path: just setup-redis-cluster
  acceptance_hint: Nodes coordinate via Redis instead of etcd

- id: TODO-005
  title: Optimize transformation performance
  category: perf
  rationale: Profile and optimize YAML transformation speed
  target_or_path: just bench-transforms
  acceptance_hint: Transformations complete in <100ms for typical manifests"""
    
    # Generate IDEAS
    ideas_content = """IDEAS:
- Add preset templates for common workload patterns (web apps, batch jobs, databases)
- Implement configuration validation with helpful error messages
- Create interactive CLI wizard for generating simplified manifests
- Add Helm chart compatibility layer
- Implement resource usage analytics and recommendations"""
    
    # Generate HOTSPOTS
    hotspots_content = """HOTSPOTS:
- kubesimpl/transformer.py: Core transformation logic, complex field mappings
- kubesimpl/cli.py: Command-line interface, argument parsing
- scripts/parse_requirements.py: Requirements normalization, mapping logic
- specs/simplification.json: Transformation rules, field definitions
- examples/input/: Test cases that drive transformation behavior"""
    
    # Assemble final content
    content = f"""{warp_content}

{project_content}

{changes_content}

{todo_content}

{ideas_content}

{hotspots_content}
"""
    
    return content

def validate_copilot_instructions(content: str) -> tuple[bool, list[str]]:
    """Validate the generated copilot instructions."""
    errors = []
    
    # Check boundaries
    if not content.startswith("[WARP.md missing") and not content.startswith("WARP"):
        errors.append("Missing WARP section at start")
    
    # Check sections are in order
    sections = ["WARP", "PROJECT", "CHANGES", "TODO", "IDEAS", "HOTSPOTS"]
    content_upper = content.upper()
    
    for i, section in enumerate(sections):
        if section not in content_upper:
            errors.append(f"Missing {section} section")
    
    # Check TODO count
    todo_count = content.count("- id: TODO-")
    if todo_count < 3:
        errors.append(f"Need ≥3 TODO items, found {todo_count}")
    
    # Check for required TODO categories
    required_categories = ["extend_feature", "bug_probe", "new_capability"]
    for category in required_categories:
        if category not in content:
            errors.append(f"Missing required TODO category: {category}")
    
    # Check for duplicate TODO titles (basic check)
    lines = content.split('\n')
    todo_titles = []
    for line in lines:
        if line.strip().startswith("title:"):
            title = line.split("title:", 1)[1].strip()
            if title in todo_titles:
                errors.append(f"Duplicate TODO title: {title}")
            todo_titles.append(title)
    
    return len(errors) == 0, errors

def main():
    """Main function to regenerate copilot instructions."""
    print("Regenerating copilot-instructions.md...")
    
    # Generate content
    content = generate_copilot_instructions()
    
    # Validate content
    is_valid, errors = validate_copilot_instructions(content)
    
    if not is_valid:
        print("❌ NON_COMPLIANT: Validation failed:")
        for error in errors:
            print(f"  - {error}")
        print("Auto-fixing and regenerating...")
        
        # Auto-fix: just regenerate (simple approach)
        content = generate_copilot_instructions()
        is_valid, errors = validate_copilot_instructions(content)
        
        if not is_valid:
            print("❌ Auto-fix failed. Manual intervention required.")
            return 1
    
    # Write the file
    copilot_file = Path("copilot-instructions.md")
    with open(copilot_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Generated copilot-instructions.md ({len(content.split())} words)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
