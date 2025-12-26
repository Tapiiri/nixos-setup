"""Tests for sync_vscode_settings module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts_py import sync_vscode_settings


def test_format_nix_value_primitives():
    """Test formatting of primitive values."""
    assert sync_vscode_settings.format_nix_value(True) == "true"
    assert sync_vscode_settings.format_nix_value(False) == "false"
    assert sync_vscode_settings.format_nix_value(42) == "42"
    assert sync_vscode_settings.format_nix_value(3.14) == "3.14"
    assert sync_vscode_settings.format_nix_value("hello") == '"hello"'
    assert sync_vscode_settings.format_nix_value(None) == "null"


def test_format_nix_value_string_escaping():
    """Test string escaping in Nix format."""
    assert sync_vscode_settings.format_nix_value('test"quote') == '"test\\"quote"'
    assert sync_vscode_settings.format_nix_value('test\\slash') == '"test\\\\slash"'
    assert sync_vscode_settings.format_nix_value('test\nline') == '"test\\nline"'


def test_format_nix_value_list():
    """Test formatting of lists."""
    assert sync_vscode_settings.format_nix_value([]) == "[]"
    result = sync_vscode_settings.format_nix_value([1, 2, 3])
    assert result == '[\n    1\n    2\n    3\n  ]'


def test_format_nix_value_dict():
    """Test formatting of dictionaries."""
    assert sync_vscode_settings.format_nix_value({}) == "{}"
    result = sync_vscode_settings.format_nix_value({"key": "value"})
    assert '"key" = "value";' in result


def test_get_managed_keys():
    """Test that managed keys are properly defined."""
    managed = sync_vscode_settings.get_managed_keys()
    assert "nix.serverPath" in managed
    assert "nix.formatterPath" in managed
    assert "editor.formatOnSave" in managed


def test_get_user_settings_filters_managed():
    """Test that user settings filtering works."""
    # Create a temporary settings file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        settings = {
            "nix.serverPath": "/nix/store/...",  # Managed - should be filtered
            "editor.formatOnSave": True,  # Managed - should be filtered
            "window.zoomLevel": 1,  # User setting - should be kept
            "telemetry.telemetryLevel": "off",  # User setting - should be kept
        }
        json.dump(settings, f)
        temp_path = Path(f.name)
    
    try:
        # Mock the settings path
        with patch('scripts_py.sync_vscode_settings.get_vscode_settings_path', return_value=temp_path):
            user_settings = sync_vscode_settings.get_user_settings()
            
            # Should not contain managed keys
            assert "nix.serverPath" not in user_settings
            assert "editor.formatOnSave" not in user_settings
            
            # Should contain user keys
            assert user_settings["window.zoomLevel"] == 1
            assert user_settings["telemetry.telemetryLevel"] == "off"
    finally:
        temp_path.unlink()


def test_generate_nix_config_empty():
    """Test generating Nix config from empty settings."""
    result = sync_vscode_settings.generate_nix_config({})
    assert "No user-specific settings detected" in result


def test_generate_nix_config_with_settings():
    """Test generating Nix config from settings."""
    settings = {
        "window.zoomLevel": 1,
        "editor.fontSize": 14,
    }
    result = sync_vscode_settings.generate_nix_config(settings)
    
    assert '"editor.fontSize" = 14;' in result
    assert '"window.zoomLevel" = 1;' in result
    assert result.startswith("  {")
    assert result.endswith("  }")


def test_get_vscode_settings_path():
    """Test VS Code settings path detection."""
    path = sync_vscode_settings.get_vscode_settings_path()
    assert str(path).endswith(".config/Code/User/settings.json")


def test_read_json_file_missing():
    """Test reading a non-existent JSON file."""
    result = sync_vscode_settings.read_json_file(Path("/nonexistent/file.json"))
    assert result == {}


def test_read_json_file_valid():
    """Test reading a valid JSON file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        data = {"test": "value"}
        json.dump(data, f)
        temp_path = Path(f.name)
    
    try:
        result = sync_vscode_settings.read_json_file(temp_path)
        assert result == {"test": "value"}
    finally:
        temp_path.unlink()


def test_read_json_file_invalid():
    """Test reading an invalid JSON file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("not valid json{")
        temp_path = Path(f.name)
    
    try:
        result = sync_vscode_settings.read_json_file(temp_path)
        assert result == {}
    finally:
        temp_path.unlink()
