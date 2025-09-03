[WARP.md missing – add strategic context]

[PROJECT.txt missing – add high-level summary]

CHANGES:
- changed: []
- added: []
- modified: []
- deleted: []
Impact: Initial setup of test automation for VMKit.

TODO:
- id: TODO-001
  title: Test basic VM creation and management commands
  category: extend_feature
  rationale: Validate core VM lifecycle operations work as expected
  target_or_path: just test-vm-lifecycle
  acceptance_hint: All basic VM operations (create, start, stop, destroy) pass tests

- id: TODO-002
  title: Test advanced resource allocation features
  category: bug_probe
  rationale: Verify percentage-based and explicit resource allocation work correctly
  target_or_path: just test-resource-alloc
  acceptance_hint: Resource allocation tests pass with various combinations

- id: TODO-003
  title: Test device passthrough capabilities
  category: new_capability
  rationale: Ensure hardware passthrough works reliably with various devices
  target_or_path: just test-passthrough
  acceptance_hint: GPU, NVMe, and other PCI device passthrough tests pass

- id: TODO-004
  title: Test network creation and management
  category: extend_feature
  rationale: Verify NAT and bridge network creation work correctly
  target_or_path: just test-networks
  acceptance_hint: Network creation, listing and deletion tests pass

- id: TODO-005
  title: Test storage repository operations
  category: bug_probe
  rationale: Validate storage repo creation and volume management
  target_or_path: just test-storage
  acceptance_hint: Storage repo and volume management tests pass

IDEAS:
- Add fuzzing tests for CLI parameter validation
- Implement performance benchmarks for VM operations
- Add stress testing for resource allocation edge cases

HOTSPOTS:
- vmkit/cli.py: Complex resource allocation logic
- vmkit/core.py: Core VM management
- vmkit/passthrough.py: Device passthrough handling
- vmkit/resources.py: Resource allocation implementation
- vmkit/storage.py: Storage management
