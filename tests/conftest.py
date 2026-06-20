"""Pytest configuration and shared fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory with default structure."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def tmp_watch_dir(tmp_path: Path) -> Path:
    """Create a temporary directory to simulate a watched folder."""
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    return watch_dir


@pytest.fixture
def tmp_dest_dir(tmp_path: Path) -> Path:
    """Create a temporary destination directory."""
    dest_dir = tmp_path / "destination"
    dest_dir.mkdir()
    return dest_dir
