"""Shared fixtures for couple-finance plugin tests."""
from pathlib import Path

import pytest

# Ensure the parent directory is importable
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import get_connection


@pytest.fixture
def tmp_db_path(tmp_path):
    """Return a temporary directory path for isolated DB testing."""
    return str(tmp_path)


@pytest.fixture
def fresh_db(tmp_db_path):
    """Create a fresh database connection with initialized schema.
    
    Yields the connection. Connection is closed after the test.
    """
    conn = get_connection(base_dir=tmp_db_path)
    yield conn
    conn.close()


class MockCtx:
    """Mock Hermes plugin context that records register_tool calls."""
    
    def __init__(self):
        self.tools = []
    
    def register_tool(self, name, toolset, schema, handler):
        self.tools.append({
            "name": name,
            "toolset": toolset,
            "schema": schema,
            "handler": handler,
        })


@pytest.fixture
def mock_ctx():
    """Provide a MockCtx instance for testing register()."""
    return MockCtx()
