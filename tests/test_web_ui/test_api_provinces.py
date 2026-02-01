"""
Test API provinces endpoints
"""

import pytest


def test_get_provinces(client):
    """Test GET /api/provinces returns all provinces"""
    response = client.get("/api/provinces")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    
    # Check required fields
    province = data[0]
    assert "province_id" in province
    assert "name" in province
    assert "population" in province
    assert "development_level" in province
    assert "loyalty" in province
    assert "stability" in province
    assert "reported_income" in province
    assert "reported_expenditure" in province
    assert "reported_surplus" in province


def test_provinces_no_debug_mode(client):
    """Test that actual values are hidden when debug mode is off"""
    # Ensure debug mode is off
    client.post("/api/debug-mode")
    
    response = client.get("/api/provinces")
    data = response.json()
    
    for province in data:
        # Actual values should not be present
        assert "actual_income" not in province
        assert "actual_expenditure" not in province
        assert "actual_surplus" not in province


def test_provinces_with_debug_mode(client):
    """Test that actual values are shown when debug mode is on"""
    # Ensure debug mode is on
    response = client.get("/api/state")
    if not response.json()["debug_mode"]:
        client.post("/api/debug-mode")
    
    response = client.get("/api/provinces")
    data = response.json()
    
    for province in data:
        # Actual values should be present
        assert "actual_income" in province
        assert "actual_expenditure" in province
        assert "actual_surplus" in province
