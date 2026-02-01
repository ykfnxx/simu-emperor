"""
Test API transfer and fund management endpoints
"""

import pytest


def test_get_province_balance(client):
    """Test GET /api/provinces/{id}/balance"""
    response = client.get("/api/provinces/1/balance")
    assert response.status_code == 200
    
    data = response.json()
    assert "province_id" in data
    assert "name" in data
    assert "balance" in data
    assert isinstance(data["balance"], float)


def test_get_allocation_ratios(client):
    """Test GET /api/allocation-ratios"""
    response = client.get("/api/allocation-ratios")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    
    ratio = data[0]
    assert "province_id" in ratio
    assert "name" in ratio
    assert "ratio" in ratio
    assert "central_share" in ratio
    assert "local_share" in ratio
    assert 0 <= ratio["ratio"] <= 1


def test_set_allocation_ratio(client):
    """Test POST /api/allocation-ratios/{id}"""
    response = client.post(
        "/api/allocation-ratios/1",
        json={"ratio": 0.7}
    )
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert data["province_id"] == 1
    assert data["ratio"] == 0.7


def test_set_allocation_ratio_invalid(client):
    """Test setting invalid allocation ratio"""
    response = client.post(
        "/api/allocation-ratios/1",
        json={"ratio": 1.5}
    )
    assert response.status_code == 400


def test_get_national_transactions(client):
    """Test GET /api/transactions/national"""
    response = client.get("/api/transactions/national")
    assert response.status_code == 200
    
    data = response.json()
    assert "transactions" in data
    assert "count" in data
    assert isinstance(data["transactions"], list)


def test_get_provincial_transactions(client):
    """Test GET /api/transactions/provincial/{id}"""
    response = client.get("/api/transactions/provincial/1")
    assert response.status_code == 200
    
    data = response.json()
    assert "province_id" in data
    assert "name" in data
    assert "transactions" in data
    assert "count" in data


def test_transfer_to_province_validation(client):
    """Test transfer to province validation"""
    # Missing amount
    response = client.post(
        "/api/transfer/to-province",
        json={"province_id": 1}
    )
    assert response.status_code == 400
    
    # Negative amount
    response = client.post(
        "/api/transfer/to-province",
        json={"province_id": 1, "amount": -100}
    )
    assert response.status_code == 400


def test_transfer_from_province_validation(client):
    """Test transfer from province validation"""
    # Missing amount
    response = client.post(
        "/api/transfer/from-province",
        json={"province_id": 1}
    )
    assert response.status_code == 400
