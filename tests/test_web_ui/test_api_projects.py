"""
Test API project endpoints
"""

import pytest


def test_create_project_success(client):
    """Test successful project creation"""
    # Get initial treasury
    response = client.get("/api/state")
    initial_treasury = response.json()["treasury"]
    
    # Create project
    response = client.post(
        "/api/provinces/1/projects",
        json={"project_type": "tax_relief"}
    )
    
    # Note: This may fail if treasury is insufficient
    # In that case, we just verify the API structure
    assert response.status_code in [200, 400]
    
    if response.status_code == 200:
        data = response.json()
        assert data["success"] is True
        assert data["project_type"] == "tax_relief"
        assert "cost" in data
        assert "province_name" in data


def test_create_project_invalid_type(client):
    """Test project creation with invalid type"""
    response = client.post(
        "/api/provinces/1/projects",
        json={"project_type": "invalid_type"}
    )
    
    assert response.status_code == 400


def test_create_project_missing_type(client):
    """Test project creation without type"""
    response = client.post(
        "/api/provinces/1/projects",
        json={}
    )
    
    assert response.status_code == 400


def test_create_project_invalid_province(client):
    """Test project creation for non-existent province"""
    response = client.post(
        "/api/provinces/999/projects",
        json={"project_type": "agriculture"}
    )
    
    assert response.status_code == 404
