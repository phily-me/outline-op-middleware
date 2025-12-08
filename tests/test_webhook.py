"""Test suite for OpenProject webhook integration."""

import hmac
import hashlib
import json
import os
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from outline_op_middleware.main import app

load_dotenv()

WEBHOOK_SECRET = os.getenv("OP_WEBHOOK_SECRET")
OP_CF_KB_REQUEST = os.getenv("OP_CF_KB_REQUEST")
OP_CF_KB_LINK = os.getenv("OP_CF_KB_LINK")


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    return TestClient(app)


def calculate_signature(payload_bytes: bytes) -> str:
    """Calculate HMAC SHA256 signature for webhook payload."""
    return hmac.new(WEBHOOK_SECRET.encode(), payload_bytes, hashlib.sha256).hexdigest()


def test_health_check(client):
    """Test health check endpoint returns correct status."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "outline-op-middleware"}


def test_valid_kb_request(client):
    """Test valid KB request without existing link initiates processing."""
    payload = {
        "action": "work_package:updated",
        "work_package": {
            "id": 12345,
            "subject": "Test Work Package - Create KB Document",
            "description": {
                "raw": "This is a test work package description.\n\nIt should be used to create a knowledge base document."
            },
            "lockVersion": 5,
            OP_CF_KB_REQUEST: True,
            OP_CF_KB_LINK: None,
            "_links": {"self": {"href": "/api/v3/work_packages/12345"}},
        },
    }

    payload_bytes = json.dumps(payload).encode("utf-8")
    signature = calculate_signature(payload_bytes)
    headers = {"X-OP-Signature": signature, "Content-Type": "application/json"}

    response = client.post("/webhook", content=payload_bytes, headers=headers)

    assert response.status_code == 200
    json_response = response.json()
    assert json_response["status"] == "processing_started"
    assert json_response["wp_id"] == 12345


def test_invalid_signature(client):
    """Test webhook with invalid signature is rejected."""
    payload = {
        "action": "work_package:updated",
        "work_package": {
            "id": 12346,
            "subject": "Test with Invalid Signature",
            OP_CF_KB_REQUEST: True,
        },
    }

    payload_bytes = json.dumps(payload).encode("utf-8")
    headers = {
        "X-OP-Signature": "invalid_signature_here",
        "Content-Type": "application/json",
    }

    response = client.post("/webhook", content=payload_bytes, headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid signature"}


def test_kb_request_false(client):
    """Test webhook with KB request flag false is ignored."""
    payload = {
        "action": "work_package:updated",
        "work_package": {
            "id": 12347,
            "subject": "Test Work Package - KB Request False",
            OP_CF_KB_REQUEST: False,
        },
    }

    payload_bytes = json.dumps(payload).encode("utf-8")
    signature = calculate_signature(payload_bytes)
    headers = {"X-OP-Signature": signature, "Content-Type": "application/json"}

    response = client.post("/webhook", content=payload_bytes, headers=headers)

    assert response.status_code == 200
    json_response = response.json()
    assert json_response["status"] == "ignored"
    assert json_response["reason"] == "kb_request not set"


def test_kb_link_exists(client):
    """Test webhook with existing KB link is ignored."""
    payload = {
        "action": "work_package:updated",
        "work_package": {
            "id": 12348,
            "subject": "Test Work Package - Link Exists",
            OP_CF_KB_REQUEST: True,
            OP_CF_KB_LINK: "https://docs.example.com/existing-document",
        },
    }

    payload_bytes = json.dumps(payload).encode("utf-8")
    signature = calculate_signature(payload_bytes)
    headers = {"X-OP-Signature": signature, "Content-Type": "application/json"}

    response = client.post("/webhook", content=payload_bytes, headers=headers)

    assert response.status_code == 200
    json_response = response.json()
    assert json_response["status"] == "ignored"
    assert json_response["reason"] == "kb_link already exists"


def test_wrong_action_type(client):
    """Test webhook with wrong action type is ignored."""
    payload = {
        "action": "work_package:created",
        "work_package": {
            "id": 12349,
            "subject": "Test Work Package - Wrong Action",
            OP_CF_KB_REQUEST: True,
        },
    }

    payload_bytes = json.dumps(payload).encode("utf-8")
    signature = calculate_signature(payload_bytes)
    headers = {"X-OP-Signature": signature, "Content-Type": "application/json"}

    response = client.post("/webhook", content=payload_bytes, headers=headers)

    assert response.status_code == 200
    json_response = response.json()
    assert json_response["status"] == "ignored"
    assert json_response["reason"] == "action 'work_package:created' not relevant"


def test_invalid_json_payload(client):
    """Test webhook with invalid JSON payload returns 400."""
    payload_bytes = b"invalid json {{"
    signature = calculate_signature(payload_bytes)
    headers = {"X-OP-Signature": signature, "Content-Type": "application/json"}

    response = client.post("/webhook", content=payload_bytes, headers=headers)

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid JSON"}


def test_missing_signature_header(client):
    """Test webhook without signature header is rejected."""
    payload = {
        "action": "work_package:updated",
        "work_package": {"id": 12350, OP_CF_KB_REQUEST: True},
    }

    payload_bytes = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    response = client.post("/webhook", content=payload_bytes, headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid signature"}
