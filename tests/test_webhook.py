#!/usr/bin/env python3
"""Test script to simulate OpenProject webhook requests."""

import hmac
import hashlib
import json
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

WEBHOOK_URL = "http://localhost:8001/webhook"
WEBHOOK_SECRET = os.getenv("OP_WEBHOOK_SECRET")
OP_CF_KB_REQUEST = os.getenv("OP_CF_KB_REQUEST")
OP_CF_KB_LINK = os.getenv("OP_CF_KB_LINK")


def calculate_signature(payload_bytes: bytes) -> str:
    """Calculate HMAC SHA256 signature for webhook payload."""
    return hmac.new(WEBHOOK_SECRET.encode(), payload_bytes, hashlib.sha256).hexdigest()


def send_webhook(payload: dict, description: str):
    """Send a webhook request with proper signature."""
    print(f"\n{'=' * 60}")
    print(f"Test: {description}")
    print(f"{'=' * 60}")

    # Convert payload to JSON bytes
    payload_json = json.dumps(payload)
    payload_bytes = payload_json.encode("utf-8")

    # Calculate signature
    signature = calculate_signature(payload_bytes)

    # Send request
    headers = {"X-OP-Signature": signature, "Content-Type": "application/json"}

    print(f"Payload: {json.dumps(payload, indent=2)}")
    print(f"Signature: {signature}")

    try:
        response = httpx.post(WEBHOOK_URL, content=payload_bytes, headers=headers)
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"\nError: {e}")


def test_valid_kb_request():
    """Test Case 1: Valid KB request without existing link."""
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
    send_webhook(payload, "Valid KB Request (should process)")


def test_invalid_signature():
    """Test Case 2: Invalid signature (should reject)."""
    payload = {
        "action": "work_package:updated",
        "work_package": {
            "id": 12346,
            "subject": "Test with Invalid Signature",
            OP_CF_KB_REQUEST: True,
        },
    }

    print(f"\n{'=' * 60}")
    print("Test: Invalid Signature (should reject)")
    print(f"{'=' * 60}")

    payload_json = json.dumps(payload)
    headers = {
        "X-OP-Signature": "invalid_signature_here",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(WEBHOOK_URL, content=payload_json, headers=headers)
        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {response.text}")
    except Exception as e:
        print(f"Error: {e}")


def test_kb_request_false():
    """Test Case 3: KB request flag is false (should ignore)."""
    payload = {
        "action": "work_package:updated",
        "work_package": {
            "id": 12347,
            "subject": "Test Work Package - KB Request False",
            OP_CF_KB_REQUEST: False,
        },
    }
    send_webhook(payload, "KB Request False (should ignore)")


def test_kb_link_exists():
    """Test Case 4: KB link already exists (should ignore)."""
    payload = {
        "action": "work_package:updated",
        "work_package": {
            "id": 12348,
            "subject": "Test Work Package - Link Exists",
            OP_CF_KB_REQUEST: True,
            OP_CF_KB_LINK: "https://docs.example.com/existing-document",
        },
    }
    send_webhook(payload, "KB Link Exists (should ignore)")


def test_wrong_action():
    """Test Case 5: Wrong action type (should ignore)."""
    payload = {
        "action": "work_package:created",
        "work_package": {
            "id": 12349,
            "subject": "Test Work Package - Wrong Action",
            OP_CF_KB_REQUEST: True,
        },
    }
    send_webhook(payload, "Wrong Action Type (should ignore)")


def test_health_check():
    """Test Case 6: Health check endpoint."""
    print(f"\n{'=' * 60}")
    print("Test: Health Check Endpoint")
    print(f"{'=' * 60}")

    try:
        response = httpx.get("http://localhost:8001/")
        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    print("Starting Webhook Tests")
    print(f"Target URL: {WEBHOOK_URL}")
    print(f"Webhook Secret: {WEBHOOK_SECRET[:10]}...")

    # Run all tests
    test_health_check()
    test_valid_kb_request()
    test_invalid_signature()
    test_kb_request_false()
    test_kb_link_exists()
    test_wrong_action()

    print(f"\n{'=' * 60}")
    print("All tests completed!")
    print(f"{'=' * 60}")
