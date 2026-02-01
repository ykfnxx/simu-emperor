"""
Test configuration for Web UI tests
"""

import pytest
from fastapi.testclient import TestClient

from ui.web.app import app, game_instance


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


@pytest.fixture
def test_game():
    """Get the global game instance"""
    global game_instance
    return game_instance
