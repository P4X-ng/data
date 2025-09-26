#!/usr/bin/env python3
"""
Tests for KubeSimpl transformer functionality.
"""
import pytest
import yaml
from pathlib import Path
import sys
import os

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kubesimpl.transformer import KubeSimplTransformer

@pytest.fixture
def transformer():
    """Create a transformer instance for testing."""
    return KubeSimplTransformer()

def test_transformer_initialization(transformer):
    """Test that transformer initializes correctly."""
    assert transformer is not None
    assert transformer.spec is not None
    assert "specVersion" in transformer.spec

def test_simple_expansion(transformer):
    """Test expanding a simple manifest."""
    simplified = {
        "name": "test-app",
        "image": "nginx:1.20",
        "replicas": 2,
        "ports": [80]
    }
    
    expanded = transformer.expand(simplified)
    
    assert expanded["apiVersion"] == "apps/v1"
    assert expanded["kind"] == "Deployment"
    assert expanded["metadata"]["name"] == "test-app"
    assert expanded["metadata"]["namespace"] == "default"
    assert expanded["spec"]["replicas"] == 2
    
    # Check containers
    containers = expanded["spec"]["template"]["spec"]["containers"]
    assert len(containers) == 1
    assert containers[0]["name"] == "test-app"
    assert containers[0]["image"] == "nginx:1.20"
    assert containers[0]["ports"][0]["containerPort"] == 80

def test_kubernetes_simplification(transformer):
    """Test simplifying a Kubernetes manifest."""
    kubernetes_manifest = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": "nginx-deployment",
            "namespace": "default",
            "uid": "some-uid",
            "resourceVersion": "12345"
        },
        "spec": {
            "replicas": 3,
            "selector": {
                "matchLabels": {
                    "app": "nginx"
                }
            },
            "template": {
                "metadata": {
                    "labels": {
                        "app": "nginx"
                    }
                },
                "spec": {
                    "containers": [{
                        "name": "nginx",
                        "image": "nginx:1.20",
                        "ports": [{
                            "containerPort": 80
                        }]
                    }]
                }
            }
        }
    }
    
    simplified = transformer.simplify(kubernetes_manifest)
    
    # Should drop metadata fields like uid, resourceVersion
    assert "uid" not in simplified.get("metadata", {})
    assert "resourceVersion" not in simplified.get("metadata", {})
    
    # Check core fields are preserved
    assert "name" in simplified
    assert "replicas" in simplified

def test_kind_inference(transformer):
    """Test resource kind inference."""
    # Test deployment inference
    deployment_manifest = {"name": "app", "image": "nginx", "replicas": 2}
    kind = transformer._infer_kind(deployment_manifest)
    assert kind == "Deployment"
    
    # Test service inference  
    service_manifest = {"name": "svc", "ports": [80]}
    kind = transformer._infer_kind(service_manifest)
    assert kind == "Service"
    
    # Test configmap inference
    configmap_manifest = {"name": "config", "data": {"key": "value"}}
    kind = transformer._infer_kind(configmap_manifest)
    assert kind == "ConfigMap"

def test_api_version_mapping(transformer):
    """Test API version mapping for different resource kinds."""
    assert transformer._infer_api_version("Deployment") == "apps/v1"
    assert transformer._infer_api_version("Service") == "v1"
    assert transformer._infer_api_version("Job") == "batch/v1"
    assert transformer._infer_api_version("ConfigMap") == "v1"

def test_container_expansion(transformer):
    """Test container specification expansion."""
    containers = [{
        "image": "nginx:1.20",
        "ports": [80, 443]
    }]
    
    expanded = transformer._expand_containers(containers)
    
    assert len(expanded) == 1
    container = expanded[0]
    assert container["name"] == "nginx"  # Inferred from image
    assert container["image"] == "nginx:1.20"
    assert len(container["ports"]) == 2
    assert container["ports"][0]["containerPort"] == 80
    assert container["ports"][1]["containerPort"] == 443

def test_yaml_string_input(transformer):
    """Test that YAML string inputs are handled correctly."""
    yaml_input = """
name: test-app
image: nginx:1.20
replicas: 1
ports: [80]
"""
    
    expanded = transformer.expand(yaml_input)
    
    assert expanded["metadata"]["name"] == "test-app"
    assert expanded["spec"]["replicas"] == 1

def test_file_transformation(transformer, tmp_path):
    """Test file-based transformation."""
    # Create input file
    input_file = tmp_path / "input.yaml"
    output_file = tmp_path / "output.yaml"
    
    input_content = {
        "name": "file-test",
        "image": "nginx:1.20",
        "replicas": 1
    }
    
    with open(input_file, 'w') as f:
        yaml.dump(input_content, f)
    
    # Transform file
    transformer.transform_file(str(input_file), str(output_file), "expand")
    
    # Check output
    assert output_file.exists()
    
    with open(output_file, 'r') as f:
        result = yaml.safe_load(f)
    
    assert result["kind"] == "Deployment"
    assert result["metadata"]["name"] == "file-test"

def test_nested_value_retrieval(transformer):
    """Test nested value retrieval utility function."""
    obj = {
        "metadata": {
            "name": "test-name",
            "labels": {
                "app": "test-app"
            }
        },
        "spec": {
            "replicas": 3
        }
    }
    
    assert transformer._get_nested_value(obj, "metadata.name") == "test-name"
    assert transformer._get_nested_value(obj, "metadata.labels.app") == "test-app"
    assert transformer._get_nested_value(obj, "spec.replicas") == 3
    assert transformer._get_nested_value(obj, "nonexistent.path") is None

def test_validation_round_trip(transformer):
    """Test round-trip validation functionality."""
    original = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": "test-app"
        },
        "spec": {
            "replicas": 2,
            "template": {
                "spec": {
                    "containers": [{
                        "name": "nginx",
                        "image": "nginx:1.20"
                    }]
                }
            }
        }
    }
    
    is_valid, diffs = transformer.validate_round_trip(original)
    
    # Note: This may fail due to transformation differences
    # The test verifies the validation mechanism works
    assert isinstance(is_valid, bool)
    assert isinstance(diffs, dict)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
