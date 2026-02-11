#!/usr/bin/env python3
"""
Quick test script to verify the API is working.
Run this with: python test_api_quick.py
"""

import httpx
import sys

API_URL = "http://localhost:8000"

def test_api():
    """Test the API endpoints."""
    print("🧪 Testing Research Swarm API...")
    print(f"📍 Base URL: {API_URL}\n")

    try:
        # Test 1: Root endpoint
        print("1️⃣  Testing root endpoint...")
        response = httpx.get(f"{API_URL}/")
        if response.status_code == 200:
            print(f"   ✅ Root endpoint working: {response.json()['name']}")
        else:
            print(f"   ❌ Root endpoint failed: {response.status_code}")
            return False

        # Test 2: Health check
        print("\n2️⃣  Testing health endpoint...")
        response = httpx.get(f"{API_URL}/api/health")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Health check passed: {data['status']}")
        else:
            print(f"   ❌ Health check failed: {response.status_code}")
            return False

        # Test 3: Analyze endpoint (with mock auth)
        print("\n3️⃣  Testing analyze endpoint (mock auth)...")
        response = httpx.post(
            f"{API_URL}/api/analyze",
            json={
                "ticker": "NVDA",
                "quarters": ["Q4_2024", "Q1_2025", "Q2_2025", "Q3_2025"],
                "news_days_back": 30
            },
            headers={"Authorization": "Bearer mock_token_123"}
        )
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Analyze endpoint working!")
            print(f"      - Job ID: {data['job_id'][:8]}...")
            print(f"      - Ticker: {data['ticker']}")
            print(f"      - Status: {data['status']}")
            print(f"      - Estimated time: {data['estimated_time_minutes']} min")
        else:
            print(f"   ❌ Analyze endpoint failed: {response.status_code}")
            print(f"      Response: {response.text}")
            return False

        print("\n✅ All tests passed!")
        print(f"\n📖 View interactive API docs: {API_URL}/api/docs")
        return True

    except httpx.ConnectError:
        print(f"\n❌ Could not connect to API at {API_URL}")
        print("\n💡 Start the API server first:")
        print("   uvicorn api.index:app --reload --port 8000")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_api()
    sys.exit(0 if success else 1)
