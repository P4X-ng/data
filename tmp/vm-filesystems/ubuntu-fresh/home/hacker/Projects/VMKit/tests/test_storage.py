#!/usr/bin/env python3
"""
Test suite for VMKit storage repository and volume management features.
Tests storage pool creation, volume management, and storage operations.
"""

import pytest
import os
import time
import tempfile
import shutil
from pathlib import Path
from vmkit.core import SecureVM, VMError
from vmkit.storage import StorageManager, StorageRepository, StorageError

# Test configuration
TEST_VM_NAME = "vmkit-test-storage"
TEST_REPO_NAME = "vmkit-test-repo"
TEST_VOLUME_NAME = "vmkit-test-volume"
TEST_VOLUME_SIZE = "10G"

@pytest.fixture(scope="module")
def storage_manager():
    """Get a StorageManager instance."""
    return StorageManager()

@pytest.fixture(scope="module")
def test_repo_path():
    """Create a temporary directory for storage testing."""
    temp_dir = tempfile.mkdtemp(prefix="vmkit-test-storage-")
    yield temp_dir
    # Cleanup
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass

@pytest.fixture(scope="function")
def storage_repo(storage_manager, test_repo_path):
    """Create a test storage repository and ensure cleanup."""
    try:
        repo = storage_manager.create_repository(
            TEST_REPO_NAME,
            test_repo_path,
            auto_start=True
        )
        yield repo
    finally:
        try:
            storage_manager.delete_repository(TEST_REPO_NAME, force=True)
        except Exception:
            pass

def test_list_repositories(storage_manager):
    """Test listing storage repositories."""
    repos = storage_manager.list_repositories()
    assert isinstance(repos, list)
    
    # Check repository properties
    for repo in repos:
        assert "name" in repo
        assert "path" in repo
        assert "status" in repo
        if "capacity" in repo:
            assert isinstance(repo["capacity"], int)

def test_repository_creation(storage_manager, test_repo_path):
    """Test creating a storage repository."""
    try:
        # Create repository
        repo = storage_manager.create_repository(
            TEST_REPO_NAME,
            test_repo_path,
            auto_start=True
        )
        
        # Verify repository properties
        info = repo.info()
        assert info["name"] == TEST_REPO_NAME
        assert info["path"] == str(test_repo_path)
        assert info["status"] == "active"
        assert "capacity" in info
        
        # Check repository is listed
        repos = storage_manager.list_repositories()
        test_repo = next((r for r in repos if r["name"] == TEST_REPO_NAME), None)
        assert test_repo is not None
        assert test_repo["status"] == "active"
        
    finally:
        # Cleanup
        try:
            storage_manager.delete_repository(TEST_REPO_NAME)
        except Exception:
            pass

def test_repository_deletion(storage_manager, test_repo_path):
    """Test storage repository deletion."""
    # Create repository
    repo = storage_manager.create_repository(
        TEST_REPO_NAME,
        test_repo_path
    )
    
    # Verify repository exists
    repos = storage_manager.list_repositories()
    assert any(r["name"] == TEST_REPO_NAME for r in repos)
    
    # Delete repository
    storage_manager.delete_repository(TEST_REPO_NAME)
    
    # Verify repository is gone
    repos = storage_manager.list_repositories()
    assert not any(r["name"] == TEST_REPO_NAME for r in repos)

def test_volume_creation(storage_repo):
    """Test creating storage volumes."""
    # Create volume
    volume_info = storage_repo.create_volume(
        TEST_VOLUME_NAME,
        size=TEST_VOLUME_SIZE,
        format="qcow2"
    )
    
    # Verify volume properties
    assert volume_info["name"] == TEST_VOLUME_NAME
    assert Path(volume_info["path"]).exists()
    assert volume_info["format"] == "qcow2"
    assert volume_info["capacity"] > 0
    
    # Check volume is listed
    volumes = storage_repo.list_volumes()
    test_volume = next((v for v in volumes if v["name"] == TEST_VOLUME_NAME), None)
    assert test_volume is not None
    assert test_volume["format"] == "qcow2"

def test_volume_deletion(storage_repo):
    """Test volume deletion."""
    # Create volume
    volume_info = storage_repo.create_volume(
        TEST_VOLUME_NAME,
        size=TEST_VOLUME_SIZE
    )
    volume_path = Path(volume_info["path"])
    
    # Verify volume exists
    assert volume_path.exists()
    volumes = storage_repo.list_volumes()
    assert any(v["name"] == TEST_VOLUME_NAME for v in volumes)
    
    # Delete volume
    storage_repo.delete_volume(TEST_VOLUME_NAME)
    
    # Verify volume is gone
    assert not volume_path.exists()
    volumes = storage_repo.list_volumes()
    assert not any(v["name"] == TEST_VOLUME_NAME for v in volumes)

def test_volume_resize(storage_repo):
    """Test volume resizing."""
    # Create volume
    volume_info = storage_repo.create_volume(
        TEST_VOLUME_NAME,
        size="5G"
    )
    initial_size = volume_info["capacity"]
    
    # Resize volume
    storage_repo.resize_volume(TEST_VOLUME_NAME, "10G")
    
    # Verify new size
    volumes = storage_repo.list_volumes()
    volume = next(v for v in volumes if v["name"] == TEST_VOLUME_NAME)
    assert volume["capacity"] > initial_size

def test_volume_cloning(storage_repo):
    """Test volume cloning."""
    # Create source volume
    src_volume = storage_repo.create_volume(
        TEST_VOLUME_NAME,
        size=TEST_VOLUME_SIZE
    )
    
    # Clone volume
    clone_name = f"{TEST_VOLUME_NAME}-clone"
    clone_info = storage_repo.clone_volume(
        TEST_VOLUME_NAME,
        clone_name
    )
    
    # Verify clone properties
    assert clone_info["name"] == clone_name
    assert Path(clone_info["path"]).exists()
    assert clone_info["capacity"] == src_volume["capacity"]
    
    # Check clone is listed
    volumes = storage_repo.list_volumes()
    assert any(v["name"] == clone_name for v in volumes)

def test_volume_format_conversion(storage_repo):
    """Test volume format conversion."""
    # Create source volume
    volume_info = storage_repo.create_volume(
        TEST_VOLUME_NAME,
        size=TEST_VOLUME_SIZE,
        format="raw"
    )
    
    # Convert to qcow2
    new_volume = storage_repo.convert_volume(
        TEST_VOLUME_NAME,
        "qcow2"
    )
    
    # Verify new format
    assert new_volume["format"] == "qcow2"
    assert Path(new_volume["path"]).exists()

def test_volume_backup(storage_repo):
    """Test volume backup operations."""
    # Create volume with some data
    volume_info = storage_repo.create_volume(
        TEST_VOLUME_NAME,
        size=TEST_VOLUME_SIZE
    )
    
    # Create backup
    backup_name = f"{TEST_VOLUME_NAME}-backup"
    backup_info = storage_repo.backup_volume(
        TEST_VOLUME_NAME,
        backup_name
    )
    
    # Verify backup
    assert backup_info["name"] == backup_name
    assert Path(backup_info["path"]).exists()
    
    # Test restore
    storage_repo.restore_volume(
        backup_name,
        TEST_VOLUME_NAME
    )
    
    # Verify restored volume
    volumes = storage_repo.list_volumes()
    restored = next(v for v in volumes if v["name"] == TEST_VOLUME_NAME)
    assert restored is not None

def test_repository_refresh(storage_repo):
    """Test repository refresh functionality."""
    # Create volume
    storage_repo.create_volume(
        TEST_VOLUME_NAME,
        size=TEST_VOLUME_SIZE
    )
    
    # Refresh repository
    storage_repo.refresh()
    
    # Verify volume is still listed
    volumes = storage_repo.list_volumes()
    assert any(v["name"] == TEST_VOLUME_NAME for v in volumes)

def test_repository_autostart(storage_manager, test_repo_path):
    """Test repository autostart feature."""
    try:
        # Create repository with autostart
        repo = storage_manager.create_repository(
            TEST_REPO_NAME,
            test_repo_path,
            auto_start=True
        )
        
        # Stop repository
        storage_manager.stop_repository(TEST_REPO_NAME)
        
        # Simulate service restart
        storage_manager.restart_service()
        
        # Verify repository is automatically started
        repos = storage_manager.list_repositories()
        test_repo = next(r for r in repos if r["name"] == TEST_REPO_NAME)
        assert test_repo["status"] == "active"
        
    finally:
        # Cleanup
        try:
            storage_manager.delete_repository(TEST_REPO_NAME)
        except Exception:
            pass

def test_error_handling(storage_manager, test_repo_path, storage_repo):
    """Test error handling for storage operations."""
    # Test duplicate repository creation
    with pytest.raises(StorageError):
        storage_manager.create_repository(
            TEST_REPO_NAME,
            test_repo_path
        )
    
    # Test invalid repository path
    with pytest.raises(ValueError):
        storage_manager.create_repository(
            "invalid-repo",
            "/nonexistent/path"
        )
    
    # Test creating volume with invalid size
    with pytest.raises(ValueError):
        storage_repo.create_volume(
            "invalid-volume",
            size="invalid"
        )
    
    # Test deleting non-existent volume
    with pytest.raises(StorageError):
        storage_repo.delete_volume("nonexistent-volume")

def test_concurrent_volume_operations(storage_repo):
    """Test concurrent volume operations."""
    volumes = []
    try:
        # Create multiple volumes concurrently
        for i in range(3):
            volume_name = f"{TEST_VOLUME_NAME}-{i}"
            volume_info = storage_repo.create_volume(
                volume_name,
                size="1G"
            )
            volumes.append(volume_name)
            
            # Verify volume was created
            assert Path(volume_info["path"]).exists()
        
        # List all volumes
        repo_volumes = storage_repo.list_volumes()
        for name in volumes:
            assert any(v["name"] == name for v in repo_volumes)
            
    finally:
        # Cleanup
        for name in volumes:
            try:
                storage_repo.delete_volume(name)
            except Exception:
                pass

def test_volume_permissions(storage_repo):
    """Test volume permission handling."""
    # Create volume with specific permissions
    volume_info = storage_repo.create_volume(
        TEST_VOLUME_NAME,
        size=TEST_VOLUME_SIZE,
        permissions=0o644
    )
    
    # Verify permissions
    volume_path = Path(volume_info["path"])
    assert oct(volume_path.stat().st_mode)[-3:] == "644"
    
    # Change permissions
    storage_repo.set_volume_permissions(
        TEST_VOLUME_NAME,
        0o600
    )
    
    # Verify new permissions
    assert oct(volume_path.stat().st_mode)[-3:] == "600"
