#!/usr/bin/env python3
"""
Generate JSON Schema for KubeSimpl simplification specification.
"""
import json
import os
from pathlib import Path

def create_simplification_schema():
    """Generate the simplification specification JSON schema."""
    
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://kubesimpl.dev/schemas/simplification-spec.schema.json",
        "title": "KubeSimpl Simplification Specification",
        "description": "Schema for defining how to simplify Kubernetes configurations",
        "type": "object",
        "required": ["specVersion", "metadata"],
        "properties": {
            "specVersion": {
                "type": "string",
                "pattern": "^[0-9]+\\.[0-9]+$",
                "description": "Version of the simplification specification format"
            },
            "metadata": {
                "type": "object",
                "required": ["project"],
                "properties": {
                    "project": {"type": "string"},
                    "description": {"type": "string"},
                    "target": {"type": "string"},
                    "language": {"type": "string"}
                }
            },
            "vocabulary": {
                "type": "object",
                "description": "Canonical terms and their synonyms for normalization",
                "patternProperties": {
                    "^[a-z-_]+$": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            },
            "resources": {
                "type": "array",
                "description": "Resource types to simplify",
                "items": {
                    "type": "object",
                    "required": ["kind"],
                    "properties": {
                        "kind": {"type": "string"},
                        "apiVersion": {"type": "string"},
                        "simplified": {"type": "boolean", "default": True}
                    }
                }
            },
            "fields": {
                "type": "object",
                "description": "Field-level transformation rules",
                "patternProperties": {
                    "^[a-zA-Z0-9._-]+$": {
                        "type": "object",
                        "properties": {
                            "required": {"type": "boolean", "default": False},
                            "default": {},
                            "description": {"type": "string"},
                            "transforms": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": ["rename", "map", "drop", "merge", "template", "compute"]
                                }
                            }
                        }
                    }
                }
            },
            "defaults": {
                "type": "object",
                "description": "Default values for simplified configurations",
                "patternProperties": {
                    "^[a-zA-Z0-9._-]+$": {}
                }
            },
            "validations": {
                "type": "array",
                "description": "Custom validation rules",
                "items": {
                    "type": "object",
                    "required": ["rule", "message"],
                    "properties": {
                        "rule": {"type": "string"},
                        "message": {"type": "string"},
                        "severity": {
                            "type": "string",
                            "enum": ["error", "warning", "info"],
                            "default": "error"
                        }
                    }
                }
            },
            "transforms": {
                "type": "object",
                "description": "Transformation rules for different operations",
                "properties": {
                    "rename": {
                        "type": "object",
                        "patternProperties": {
                            "^[a-zA-Z0-9._-]+$": {"type": "string"}
                        }
                    },
                    "map": {
                        "type": "object",
                        "patternProperties": {
                            "^[a-zA-Z0-9._-]+$": {
                                "type": "object",
                                "patternProperties": {
                                    ".*": {"type": "string"}
                                }
                            }
                        }
                    },
                    "drop": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "merge": {
                        "type": "object",
                        "patternProperties": {
                            "^[a-zA-Z0-9._-]+$": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        }
                    },
                    "template": {
                        "type": "object",
                        "patternProperties": {
                            "^[a-zA-Z0-9._-]+$": {"type": "string"}
                        }
                    },
                    "compute": {
                        "type": "object",
                        "patternProperties": {
                            "^[a-zA-Z0-9._-]+$": {"type": "string"}
                        }
                    }
                }
            },
            "constraints": {
                "type": "array",
                "description": "Business logic constraints",
                "items": {
                    "type": "object",
                    "required": ["name", "condition"],
                    "properties": {
                        "name": {"type": "string"},
                        "condition": {"type": "string"},
                        "action": {
                            "type": "string",
                            "enum": ["reject", "warn", "fix"],
                            "default": "reject"
                        }
                    }
                }
            },
            "presets": {
                "type": "object",
                "description": "Predefined configuration presets",
                "patternProperties": {
                    "^[a-zA-Z0-9._-]+$": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "config": {"type": "object"}
                        }
                    }
                }
            },
            "examples": {
                "type": "array",
                "description": "Example transformations",
                "items": {
                    "type": "object",
                    "required": ["name", "input", "output"],
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "input": {},
                        "output": {}
                    }
                }
            },
            "removals": {
                "type": "object",
                "description": "Components and features to remove",
                "properties": {
                    "components": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "features": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            },
            "replacements": {
                "type": "object",
                "description": "Component replacement mappings",
                "patternProperties": {
                    "^[a-zA-Z0-9._-]+$": {
                        "type": "object",
                        "properties": {
                            "from": {"type": "string"},
                            "to": {"type": "string"}
                        }
                    }
                }
            },
            "access_control": {
                "type": "object",
                "description": "Access control model definitions",
                "patternProperties": {
                    "^[a-zA-Z0-9._-]+$": {
                        "type": "object",
                        "properties": {
                            "permissions": {"type": "string"},
                            "method": {"type": "string"},
                            "description": {"type": "string"}
                        }
                    }
                }
            },
            "networking": {
                "type": "object",
                "description": "Networking configuration",
                "properties": {
                    "api": {
                        "type": "object",
                        "properties": {
                            "protocol": {"type": "string"},
                            "bind": {"type": "string"},
                            "protection": {"type": "string"},
                            "ssl": {"type": "string"}
                        }
                    },
                    "containers": {
                        "type": "object",
                        "properties": {
                            "mode": {"type": "string"},
                            "pod_subnet": {"type": "string"},
                            "isolation": {"type": "string"}
                        }
                    }
                }
            }
        }
    }
    
    # Ensure schemas directory exists
    schema_dir = Path("schemas")
    schema_dir.mkdir(exist_ok=True)
    
    # Write schema file
    schema_path = schema_dir / "simplification-spec.schema.json"
    with open(schema_path, 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2, sort_keys=True)
    
    print(f"Generated schema: {schema_path}")
    return schema_path

if __name__ == "__main__":
    create_simplification_schema()
