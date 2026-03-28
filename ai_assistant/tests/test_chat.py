import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_chat_general_response():
    """Test that the assistant responds correctly to a general greeting."""
    payload = {
        "message": "Hello, who are you?",
        "user_id": "user_123"
    }
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "Iyobo" in data["reply"]
    assert data["intent"] == "general"

def test_chat_payment_intent():
    """Test that mentions of Idia Coin trigger payment help."""
    payload = {"message": "Tell me about Idia Coin"}
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "payment_help" in data["intent"]
    assert "Idia Coin" in data["reply"]

def test_chat_order_intent():
    """Test that mentions of orders or carts trigger order help."""
    payload = {"message": "Where is my order?"}
    response = client.post("/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "order_help"

def test_chat_validation_empty_message():
    """Test that an empty message results in a 422 Validation Error."""
    payload = {"message": ""}
    response = client.post("/chat", json=payload)
    assert response.status_code == 422

def test_chat_missing_required_field():
    """Test that missing the message field results in a 422 error."""
    payload = {"user_id": "user_123"}
    response = client.post("/chat", json=payload)
    assert response.status_code == 422