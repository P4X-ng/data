#!/usr/bin/env python3
"""
Basic CLI tests for VMKit
"""

import pytest
from click.testing import CliRunner
from vmkit.cli import vmkit

def test_cli_help():
    """Test that CLI help works"""
    runner = CliRunner()
    result = runner.invoke(vmkit, ['--help'])
    assert result.exit_code == 0
    assert 'VMKit - Simple Secure Boot VM management' in result.output

def test_cli_version():
    """Test that CLI version works"""
    runner = CliRunner()
    result = runner.invoke(vmkit, ['--version'])
    assert result.exit_code == 0

def test_list_command():
    """Test list command (should work even without VMs)"""
    runner = CliRunner()
    result = runner.invoke(vmkit, ['list'])
    # Should exit gracefully even if libvirt is not available
    assert result.exit_code in [0, 1]

if __name__ == "__main__":
    pytest.main([__file__])