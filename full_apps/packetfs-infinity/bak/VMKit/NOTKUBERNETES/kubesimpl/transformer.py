#!/usr/bin/env python3
"""
KubeSimpl Transformer - Bidirectional Kubernetes YAML transformer.
"""
import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import re

class KubeSimplTransformer:
    """Bidirectional transformer between simplified and canonical Kubernetes manifests."""
    
    def __init__(self, spec_path: str = "specs/simplification.json"):
        """Initialize transformer with specification."""
        self.spec = self._load_spec(spec_path)
        
    def _load_spec(self, spec_path: str) -> Dict[str, Any]:
        """Load the simplification specification."""
        path = Path(spec_path)
        if not path.exists():
            raise FileNotFoundError(f"Specification not found: {spec_path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def simplify(self, kubernetes_manifest: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        """Transform canonical Kubernetes manifest to simplified format."""
        if isinstance(kubernetes_manifest, str):
            manifest = yaml.safe_load(kubernetes_manifest)
        else:
            manifest = kubernetes_manifest.copy()
        
        simplified = {}
        
        # Apply field transformations from spec
        transforms = self.spec.get("transforms", {})
        rename_map = transforms.get("rename", {})
        drop_fields = transforms.get("drop", [])
        
        # Process the manifest
        self._apply_simplification_rules(manifest, simplified, rename_map, drop_fields)
        
        return simplified
    
    def expand(self, simplified_manifest: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        """Transform simplified manifest to canonical Kubernetes format.
        
        Also checks if this is already a K8s manifest and warns about unsupported fields.
        """
        if isinstance(simplified_manifest, str):
            manifest = yaml.safe_load(simplified_manifest)
        else:
            manifest = simplified_manifest.copy()
        
        # Check if this is already a K8s manifest
        if self._is_kubernetes_manifest(manifest):
            return self._process_kubernetes_manifest(manifest)
        
        # Determine resource type from simplified manifest
        kind = self._infer_kind(manifest)
        api_version = self._infer_api_version(kind)
        
        # Start with basic structure
        expanded = {
            "apiVersion": api_version,
            "kind": kind,
            "metadata": {},
            "spec": {}
        }
        
        # Apply expansion rules
        self._apply_expansion_rules(manifest, expanded)
        
        return expanded
    
    def _apply_simplification_rules(self, source: Dict[str, Any], target: Dict[str, Any], 
                                   rename_map: Dict[str, str], drop_fields: List[str]):
        """Apply simplification transformation rules."""
        transforms = self.spec.get("transforms", {})
        
        for key, value in source.items():
            # Skip dropped fields
            if key in drop_fields or any(key.startswith(drop) for drop in drop_fields):
                continue
            
            # Apply rename mappings
            target_key = rename_map.get(key, key)
            
            if isinstance(value, dict):
                if target_key not in target:
                    target[target_key] = {}
                self._apply_simplification_rules(value, target[target_key], rename_map, drop_fields)
            elif isinstance(value, list):
                target[target_key] = [self._simplify_item(item, rename_map, drop_fields) for item in value]
            else:
                target[target_key] = value
    
    def _simplify_item(self, item: Any, rename_map: Dict[str, str], drop_fields: List[str]) -> Any:
        """Simplify a single item (used for lists)."""
        if isinstance(item, dict):
            simplified = {}
            self._apply_simplification_rules(item, simplified, rename_map, drop_fields)
            return simplified
        return item
    
    def _apply_expansion_rules(self, simplified: Dict[str, Any], expanded: Dict[str, Any]):
        """Apply expansion transformation rules."""
        defaults = self.spec.get("defaults", {})
        transforms = self.spec.get("transforms", {})
        
        # Extract basic fields
        name = simplified.get("name", simplified.get("metadata", {}).get("name", "unnamed"))
        namespace = simplified.get("namespace", "default")
        
        # Set metadata
        expanded["metadata"] = {
            "name": name,
            "namespace": namespace,
            "labels": {"app": name}
        }
        
        # Handle containers (the core simplification)
        if "containers" in simplified:
            expanded["spec"]["template"] = {
                "metadata": {"labels": {"app": name}},
                "spec": {"containers": self._expand_containers(simplified["containers"])}
            }
            expanded["spec"]["selector"] = {"matchLabels": {"app": name}}
            
        # Handle replicas
        if "replicas" in simplified:
            expanded["spec"]["replicas"] = simplified["replicas"]
        else:
            expanded["spec"]["replicas"] = defaults.get("spec.replicas", 1)
        
        # Handle single container shorthand
        if "image" in simplified:
            container = {
                "name": name,
                "image": simplified["image"]
            }
            if "ports" in simplified:
                container["ports"] = [{"containerPort": port} for port in simplified["ports"]]
            
            expanded["spec"]["template"] = {
                "metadata": {"labels": {"app": name}},
                "spec": {"containers": [container]}
            }
            expanded["spec"]["selector"] = {"matchLabels": {"app": name}}
    
    def _expand_containers(self, containers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Expand simplified container specs."""
        expanded_containers = []
        
        for container in containers:
            expanded_container = container.copy()
            
            # Ensure name is set
            if "name" not in expanded_container:
                expanded_container["name"] = expanded_container.get("image", "container").split(":")[0]
            
            # Expand ports if simplified
            if "ports" in expanded_container and isinstance(expanded_container["ports"][0], int):
                expanded_container["ports"] = [
                    {"containerPort": port} for port in expanded_container["ports"]
                ]
            
            expanded_containers.append(expanded_container)
        
        return expanded_containers
    
    def _infer_kind(self, manifest: Dict[str, Any]) -> str:
        """Infer Kubernetes resource kind from simplified manifest."""
        if "kind" in manifest:
            return manifest["kind"]
        
        # Heuristics based on simplified config
        if "replicas" in manifest or "containers" in manifest or "image" in manifest:
            return "Deployment"
        elif "ports" in manifest and "selector" not in manifest:
            return "Service"
        elif "data" in manifest:
            return "ConfigMap"
        
        return "Deployment"  # Default
    
    def _infer_api_version(self, kind: str) -> str:
        """Get appropriate API version for resource kind."""
        api_versions = {
            "Deployment": "apps/v1",
            "StatefulSet": "apps/v1", 
            "DaemonSet": "apps/v1",
            "Job": "batch/v1",
            "CronJob": "batch/v1",
            "Service": "v1",
            "ConfigMap": "v1",
            "Secret": "v1",
            "Pod": "v1"
        }
        return api_versions.get(kind, "v1")
    
    def _is_kubernetes_manifest(self, manifest: Dict[str, Any]) -> bool:
        """Check if this is already a Kubernetes manifest."""
        api_version = manifest.get("apiVersion", "")
        kind = manifest.get("kind", "")
        
        # Check for K8s API versions
        k8s_api_patterns = [
            "apps/", "batch/", "v1", "v1beta", "v1alpha",
            "networking.k8s.io", "storage.k8s.io", "rbac.authorization.k8s.io"
        ]
        
        return any(pattern in api_version for pattern in k8s_api_patterns) and kind
    
    def _process_kubernetes_manifest(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        """Process an existing K8s manifest, warning about unsupported fields."""
        kind = manifest.get("kind", "Unknown")
        name = manifest.get("metadata", {}).get("name", "unnamed")
        
        # Unsupported resource types (we ignore these completely)
        ignored_kinds = [
            "ServiceAccount", "Role", "RoleBinding", "ClusterRole", "ClusterRoleBinding",
            "NetworkPolicy", "PodSecurityPolicy", "PodDisruptionBudget",
            "HorizontalPodAutoscaler", "VerticalPodAutoscaler",
            "CustomResourceDefinition", "MutatingWebhookConfiguration", "ValidatingWebhookConfiguration"
        ]
        
        if kind in ignored_kinds:
            print(f"⚠️  Ignoring {kind}: {name} (not supported in NK)")
            return None
        
        # For supported types, warn about complex fields
        if kind == "Deployment" or kind == "StatefulSet":
            self._warn_deployment_fields(manifest)
        elif kind == "Service":
            self._warn_service_fields(manifest)
        
        # Simplify the manifest
        simplified = self._extract_essentials(manifest)
        return simplified
    
    def _warn_deployment_fields(self, manifest: Dict[str, Any]):
        """Warn about unsupported Deployment/StatefulSet fields."""
        spec = manifest.get("spec", {})
        name = manifest.get("metadata", {}).get("name", "unnamed")
        
        # Check for unsupported fields
        if "strategy" in spec:
            print(f"⚠️  {name}: Ignoring spec.strategy (NK uses simple restart)")
        
        template_spec = spec.get("template", {}).get("spec", {})
        if "affinity" in template_spec:
            print(f"⚠️  {name}: Ignoring pod affinity rules")
        if "tolerations" in template_spec:
            print(f"⚠️  {name}: Ignoring pod tolerations")
        if "securityContext" in template_spec:
            print(f"⚠️  {name}: Ignoring security context")
        if "serviceAccountName" in template_spec:
            print(f"⚠️  {name}: Ignoring service account")
        
        # Check containers for unsupported fields
        containers = template_spec.get("containers", [])
        for container in containers:
            if "resources" in container:
                print(f"⚠️  {name}: Ignoring resource limits/requests")
            if "livenessProbe" in container or "readinessProbe" in container:
                print(f"⚠️  {name}: Ignoring health probes")
            if "securityContext" in container:
                print(f"⚠️  {name}: Ignoring container security context")
    
    def _warn_service_fields(self, manifest: Dict[str, Any]):
        """Warn about unsupported Service fields."""
        spec = manifest.get("spec", {})
        name = manifest.get("metadata", {}).get("name", "unnamed")
        
        svc_type = spec.get("type", "ClusterIP")
        if svc_type not in ["ClusterIP", "NodePort"]:
            print(f"⚠️  {name}: Service type {svc_type} not fully supported (treating as ClusterIP)")
        
        if "sessionAffinity" in spec:
            print(f"⚠️  {name}: Ignoring session affinity")
    
    def _extract_essentials(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        """Extract only the essential fields NK can handle."""
        kind = manifest.get("kind")
        
        essentials = {
            "apiVersion": "notkubernetes/v1",
            "kind": "App" if kind in ["Deployment", "StatefulSet"] else kind,
            "metadata": {
                "name": manifest.get("metadata", {}).get("name", "unnamed"),
                "namespace": manifest.get("metadata", {}).get("namespace", "default")
            }
        }
        
        if kind in ["Deployment", "StatefulSet", "DaemonSet"]:
            spec = manifest.get("spec", {})
            essentials["spec"] = {
                "replicas": spec.get("replicas", 1)
            }
            
            # Extract containers
            template = spec.get("template", {})
            containers = template.get("spec", {}).get("containers", [])
            if containers:
                essentials["spec"]["template"] = {
                    "spec": {
                        "containers": [
                            {
                                "name": c.get("name", "container"),
                                "image": c.get("image", "nginx"),
                                "ports": c.get("ports", [])
                            }
                            for c in containers
                        ]
                    }
                }
        
        return essentials
    
    def transform_file(self, input_path: str, output_path: str, direction: str = "expand"):
        """Transform a file from one format to another."""
        input_file = Path(input_path)
        output_file = Path(output_path)
        
        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Read input
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Handle multiple documents in YAML
        documents = list(yaml.safe_load_all(content))
        
        # Transform each document
        transformed_docs = []
        for doc in documents:
            if doc is None:
                continue
                
            if direction == "expand":
                transformed = self.expand(doc)
            elif direction == "simplify":
                transformed = self.simplify(doc)
            else:
                raise ValueError(f"Unknown direction: {direction}")
            
            transformed_docs.append(transformed)
        
        # Write output
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump_all(transformed_docs, f, default_flow_style=False, sort_keys=False)
        
        print(f"Transformed {len(transformed_docs)} document(s): {input_path} -> {output_path}")
    
    def validate_round_trip(self, original: Dict[str, Any]) -> tuple[bool, Dict[str, Any]]:
        """Validate round-trip transformation fidelity."""
        try:
            # Original -> Simplified -> Expanded
            simplified = self.simplify(original)
            expanded = self.expand(simplified)
            
            # Check if essential fields match
            essential_fields = ["metadata.name", "spec.containers", "spec.replicas"]
            
            diffs = {}
            for field_path in essential_fields:
                orig_val = self._get_nested_value(original, field_path)
                exp_val = self._get_nested_value(expanded, field_path)
                
                if orig_val != exp_val:
                    diffs[field_path] = {"original": orig_val, "expanded": exp_val}
            
            return len(diffs) == 0, diffs
            
        except Exception as e:
            return False, {"error": str(e)}
    
    def _get_nested_value(self, obj: Dict[str, Any], path: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        keys = path.split(".")
        current = obj
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current
