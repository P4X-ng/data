#!/usr/bin/env python3
"""
Parse requirements into normalized simplification specification.
"""
import json
from pathlib import Path
from typing import Dict, Any, List

def normalize_requirements(requirements: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize the requirements to match our specification schema."""
    
    # Define vocabulary for term normalization
    vocabulary = {
        "container": ["pod", "workload", "compute-unit"],
        "storage": ["disk", "volume", "pv", "pvc"],
        "network": ["networking", "connectivity", "service-mesh"],
        "security": ["auth", "authentication", "authorization", "rbac"],
        "orchestration": ["scheduling", "deployment", "management"],
        "monitoring": ["observability", "metrics", "logging", "health-checks"]
    }
    
    # Create normalized specification
    spec = {
        "specVersion": requirements.get("specVersion", "1.0"),
        "metadata": requirements.get("metadata", {}),
        "vocabulary": vocabulary,
        
        # Resources that will be simplified
        "resources": [
            {"kind": "Pod", "apiVersion": "v1", "simplified": True},
            {"kind": "Deployment", "apiVersion": "apps/v1", "simplified": True},
            {"kind": "Service", "apiVersion": "v1", "simplified": True},
            {"kind": "ConfigMap", "apiVersion": "v1", "simplified": True},
            {"kind": "Secret", "apiVersion": "v1", "simplified": True},
            {"kind": "StatefulSet", "apiVersion": "apps/v1", "simplified": True},
            {"kind": "Job", "apiVersion": "batch/v1", "simplified": True},
            {"kind": "CronJob", "apiVersion": "batch/v1", "simplified": True}
        ],
        
        # Field transformation rules
        "fields": {
            "metadata.name": {
                "required": True,
                "description": "Resource name"
            },
            "metadata.namespace": {
                "required": False,
                "default": "default",
                "description": "Kubernetes namespace"
            },
            "spec.replicas": {
                "required": False,
                "default": 1,
                "description": "Number of replicas"
            },
            "spec.containers": {
                "required": True,
                "description": "Container specifications"
            },
            "spec.selector": {
                "required": False,
                "transforms": ["compute"],
                "description": "Auto-generated selector"
            }
        },
        
        # Default values for simplified configs
        "defaults": {
            "apiVersion": "v1",
            "kind": "Container",
            "metadata.namespace": "default",
            "spec.replicas": 1,
            "spec.restartPolicy": "Always",
            "spec.containers[].imagePullPolicy": "IfNotPresent"
        },
        
        # Transformation rules
        "transforms": {
            "rename": {
                "spec.containers": "containers",
                "spec.replicas": "replicas",
                "metadata.name": "name",
                "metadata.namespace": "namespace"
            },
            "drop": [
                "metadata.uid",
                "metadata.resourceVersion",
                "metadata.generation",
                "metadata.creationTimestamp",
                "metadata.managedFields",
                "status"
            ],
            "compute": {
                "spec.selector": "matchLabels: {app: '${metadata.name}'}"
            },
            "template": {
                "metadata.labels": "{app: '${metadata.name}'}"
            }
        },
        
        # Business constraints
        "constraints": [
            {
                "name": "require_name",
                "condition": "metadata.name != null",
                "action": "reject"
            },
            {
                "name": "container_image_required", 
                "condition": "all(containers, .image != null)",
                "action": "reject"
            }
        ],
        
        # Configuration presets
        "presets": {
            "web-app": {
                "description": "Standard web application",
                "config": {
                    "replicas": 3,
                    "containers": [{
                        "ports": [{"containerPort": 8080}]
                    }]
                }
            },
            "batch-job": {
                "description": "Batch processing job",
                "config": {
                    "kind": "Job",
                    "spec": {
                        "completions": 1,
                        "parallelism": 1
                    }
                }
            }
        }
    }
    
    # Add KubeSimpl-specific sections from requirements
    if "removals" in requirements:
        spec["removals"] = requirements["removals"]
    
    if "replacements" in requirements:
        spec["replacements"] = requirements["replacements"]
        
    if "access_control" in requirements:
        spec["access_control"] = requirements["access_control"]
        
    if "networking" in requirements:
        spec["networking"] = requirements["networking"]
        
    if "deployment" in requirements:
        spec["deployment"] = requirements["deployment"]
        
    if "container_runtime" in requirements:
        spec["container_runtime"] = requirements["container_runtime"]
        
    if "simplified_resources" in requirements:
        spec["simplified_resources"] = requirements["simplified_resources"]
        
    if "job_system" in requirements:
        spec["job_system"] = requirements["job_system"]
        
    if "configuration" in requirements:
        spec["configuration"] = requirements["configuration"]
        
    if "performance" in requirements:
        spec["performance"] = requirements["performance"]
        
    if "kubectl_integration" in requirements:
        spec["kubectl_integration"] = requirements["kubectl_integration"]
    
    return spec

def parse_requirements_file():
    """Parse requirements from input file and generate specification."""
    
    # Look for requirements file
    input_files = [
        Path("input/requirements.json"),
        Path("input/requirements.yaml"),
        Path("input/requirements.yml"),
        Path("input/requirements.md")
    ]
    
    requirements_file = None
    for f in input_files:
        if f.exists():
            requirements_file = f
            break
    
    if not requirements_file:
        print("No requirements file found in input/")
        return
    
    print(f"Parsing requirements from: {requirements_file}")
    
    # Parse based on file type
    if requirements_file.suffix == ".json":
        with open(requirements_file, 'r', encoding='utf-8') as f:
            requirements = json.load(f)
    else:
        print(f"Unsupported file format: {requirements_file.suffix}")
        return
    
    # Normalize to specification format
    spec = normalize_requirements(requirements)
    
    # Ensure specs directory exists
    specs_dir = Path("specs")
    specs_dir.mkdir(exist_ok=True)
    
    # Write normalized specification
    spec_path = specs_dir / "simplification.json"
    with open(spec_path, 'w', encoding='utf-8') as f:
        json.dump(spec, f, indent=2, sort_keys=True)
    
    print(f"Generated specification: {spec_path}")
    
    # Log any unmapped items for triage
    unmapped_items = []
    for key in requirements:
        if key not in ["specVersion", "metadata", "removals", "replacements", 
                      "access_control", "networking", "deployment", "container_runtime",
                      "simplified_resources", "job_system", "configuration", 
                      "performance", "kubectl_integration"]:
            unmapped_items.append(key)
    
    if unmapped_items:
        print(f"Unmapped items for triage: {unmapped_items}")
    
    return spec_path

if __name__ == "__main__":
    parse_requirements_file()
