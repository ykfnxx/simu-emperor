"""
Test API state endpoints
"""

import pytest


def test_get_state(client):
    """Test GET /api/state returns correct format"""
    response = client.get("/api/state")
    assert response.status_code == 200
    
    data = response.json()
    assert "month" in data
    assert "treasury" in data
    assert "debug_mode" in data
    assert "national_event_count" in data
    assert "province_event_count" in data
    
    assert isinstance(data["month"], int)
    assert isinstance(data["treasury"], float)
    assert isinstance(data["debug_mode"], bool)


def test_next_month(client):
    """Test POST /api/next-month advances month"""
    # Get initial state
    response = client.get("/api/state")
    initial_month = response.json()["month"]
    
    # Advance month
    response = client.post("/api/next-month")
    assert response.status_code == 200
    
    data = response.json()
    assert data["month"] == initial_month + 1


def test_toggle_debug_mode(client):
    """Test POST /api/debug-mode toggles debug mode"""
    # Get initial state
    response = client.get("/api/state")
    initial_debug = response.json()["debug_mode"]
    
    # Toggle debug mode
    response = client.post("/api/debug-mode")
    assert response.status_code == 200
    
    data = response.json()
    assert data["debug_mode"] == (not initial_debug)
    
    # Toggle back
    response = client.post("/api/debug-mode")
    assert response.status_code == 200
    assert response.json()["debug_mode"] == initial_debug


def test_state_persistence(client):
    """Test state persists across requests"""
    # Get initial state
    response = client.get("/api/state")
    initial_data = response.json()
    
    # Advance month
    client.post("/api/next-month")
    
    # Get state again
    response = client.get("/api/state")
    new_data = response.json()
    
    assert new_data["month"] == initial_data["month"] + 1
