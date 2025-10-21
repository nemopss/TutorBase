#!/usr/bin/env python3
"""
Test Tenant Switching
This script tests the tenant switching functionality end-to-end
"""

import base64
import json
import sys
from typing import Optional

import requests

API_URL = "http://localhost:8001/api/v1"


def decode_jwt(token: str) -> dict:
    """Decode JWT token payload"""
    try:
        # Split token and get payload
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")
        
        payload_b64 = parts[1]
        
        # Add padding if needed
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += '=' * padding
        
        # Decode base64
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_bytes)
        
        return payload
    except Exception as e:
        print(f"   ✗ Failed to decode JWT: {e}")
        return {}


def test_tenant_switching():
    """Test tenant switching end-to-end"""
    
    print("=" * 50)
    print("Testing Tenant Switching")
    print("=" * 50)
    print()
    
    # Step 1: Login as super-admin
    print("1. Logging in as super-admin...")
    try:
        response = requests.post(
            f"{API_URL}/auth/login",
            json={"init_data": "dev"}
        )
        response.raise_for_status()
        login_data = response.json()
        
        initial_token = login_data['access_token']
        user_name = login_data['user']['display_name']
        user_role = login_data['user']['role']
        
        print(f"   ✓ Logged in as: {user_name} (role: {user_role})")
    except Exception as e:
        print(f"   ✗ Login failed: {e}")
        return False
    print()
    
    # Step 2: Decode initial JWT
    print("2. Decoding initial JWT...")
    initial_payload = decode_jwt(initial_token)
    initial_tenant_id = initial_payload.get('tenant_id')
    
    print(f"   Initial tenant_id: {initial_tenant_id}")
    print(f"   Full payload: {json.dumps(initial_payload, indent=2)}")
    print()
    
    # Step 3: Get list of tenants
    print("3. Fetching available tenants...")
    try:
        response = requests.get(
            f"{API_URL}/tenants",
            headers={"Authorization": f"Bearer {initial_token}"}
        )
        response.raise_for_status()
        tenants_data = response.json()
        
        print("   Available tenants:")
        for tenant in tenants_data['items']:
            print(f"     - {tenant['name']} (id: {tenant['id']}, active: {tenant['is_active']})")
    except Exception as e:
        print(f"   ✗ Failed to fetch tenants: {e}")
        return False
    print()
    
    # Step 4: Switch to tenant 1
    print("4. Switching to tenant 1...")
    try:
        response = requests.post(
            f"{API_URL}/auth/switch-tenant",
            headers={"Authorization": f"Bearer {initial_token}"},
            json={"tenant_id": 1}
        )
        response.raise_for_status()
        switch_data = response.json()
        
        new_token = switch_data['access_token']
        print("   ✓ Received new token")
    except Exception as e:
        print(f"   ✗ Tenant switch failed: {e}")
        if hasattr(e, 'response'):
            print(f"   Response: {e.response.text}")
        return False
    print()
    
    # Step 5: Decode new JWT
    print("5. Decoding new JWT...")
    new_payload = decode_jwt(new_token)
    new_tenant_id = new_payload.get('tenant_id')
    
    print(f"   New tenant_id: {new_tenant_id}")
    print(f"   Full payload: {json.dumps(new_payload, indent=2)}")
    print()
    
    # Step 6: Verify tenant_id changed
    if new_tenant_id == 1:
        print("   ✓ Tenant switch successful! tenant_id is now 1")
    else:
        print(f"   ✗ Tenant switch failed! tenant_id is {new_tenant_id} (expected 1)")
        return False
    print()
    
    # Step 7: Verify data filtering
    print("6. Verifying data filtering...")
    try:
        response = requests.get(
            f"{API_URL}/learners",
            headers={"Authorization": f"Bearer {new_token}"}
        )
        response.raise_for_status()
        learners_data = response.json()
        
        learner_count = len(learners_data['items'])
        tenant_ids = set(learner['tenant_id'] for learner in learners_data['items'])
        
        print(f"   Found {learner_count} learners")
        print(f"   Tenant IDs in results: {tenant_ids}")
        
        if tenant_ids == {1}:
            print("   ✓ Data correctly filtered to tenant 1")
        else:
            print(f"   ✗ Data filtering issue! Found tenant IDs: {tenant_ids}")
            return False
    except Exception as e:
        print(f"   ✗ Failed to fetch learners: {e}")
        return False
    print()
    
    # Step 8: Switch back to global view
    print("7. Switching back to global view...")
    try:
        response = requests.post(
            f"{API_URL}/auth/switch-tenant",
            headers={"Authorization": f"Bearer {new_token}"},
            json={"tenant_id": None}
        )
        response.raise_for_status()
        global_data = response.json()
        
        global_token = global_data['access_token']
        global_payload = decode_jwt(global_token)
        global_tenant_id = global_payload.get('tenant_id')
        
        print(f"   Global tenant_id: {global_tenant_id}")
        
        if global_tenant_id is None:
            print("   ✓ Switched back to global view")
        else:
            print(f"   ✗ Failed to switch to global view! tenant_id is {global_tenant_id}")
            return False
    except Exception as e:
        print(f"   ✗ Failed to switch to global: {e}")
        return False
    print()
    
    # Step 9: Verify global data access
    print("8. Verifying global data access...")
    try:
        response = requests.get(
            f"{API_URL}/learners",
            headers={"Authorization": f"Bearer {global_token}"}
        )
        response.raise_for_status()
        global_learners = response.json()
        
        global_count = len(global_learners['items'])
        global_tenant_ids = set(learner['tenant_id'] for learner in global_learners['items'])
        
        print(f"   Found {global_count} learners")
        print(f"   Tenant IDs in results: {global_tenant_ids}")
        
        if global_count > learner_count:
            print("   ✓ Global view shows more data than tenant-specific view")
        else:
            print("   ⚠ Warning: Global view has same or less data than tenant view")
    except Exception as e:
        print(f"   ✗ Failed to fetch global learners: {e}")
        return False
    print()
    
    # Summary
    print("=" * 50)
    print("✓ All tests passed!")
    print("=" * 50)
    print()
    print("Summary:")
    print(f"  • Initial tenant_id: {initial_tenant_id}")
    print(f"  • After switch to tenant 1: {new_tenant_id}")
    print(f"  • After switch to global: {global_tenant_id}")
    print(f"  • Tenant 1 learners: {learner_count}")
    print(f"  • Global learners: {global_count}")
    print()
    
    return True


if __name__ == "__main__":
    success = test_tenant_switching()
    sys.exit(0 if success else 1)
