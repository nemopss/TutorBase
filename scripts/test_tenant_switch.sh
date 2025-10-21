#!/bin/bash

# Test Tenant Switching
# This script tests the tenant switching functionality end-to-end

set -e

API_URL="${API_URL:-http://localhost:8001/api/v1}"

echo "========================================="
echo "Testing Tenant Switching"
echo "========================================="
echo ""

# Step 1: Login as super-admin
echo "1. Logging in as super-admin..."
LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"init_data": "dev"}')

INITIAL_TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')
USER_NAME=$(echo $LOGIN_RESPONSE | jq -r '.user.display_name')
USER_ROLE=$(echo $LOGIN_RESPONSE | jq -r '.user.role')

echo "   ✓ Logged in as: $USER_NAME (role: $USER_ROLE)"
echo ""

# Step 2: Decode initial JWT
echo "2. Decoding initial JWT..."
INITIAL_B64=$(echo $INITIAL_TOKEN | cut -d'.' -f2)
# Add padding if needed
INITIAL_B64_PADDED=$(echo "$INITIAL_B64" | awk '{while (length($0) % 4 != 0) $0 = $0 "="; print}')
INITIAL_PAYLOAD=$(echo "$INITIAL_B64_PADDED" | base64 -d 2>/dev/null || echo "$INITIAL_B64_PADDED" | base64 -D 2>/dev/null)
INITIAL_TENANT_ID=$(echo "$INITIAL_PAYLOAD" | jq -r '.tenant_id')

echo "   Initial tenant_id: $INITIAL_TENANT_ID"
echo "   Full payload:"
echo "$INITIAL_PAYLOAD" | jq '.'
echo ""

# Step 3: Get list of tenants
echo "3. Fetching available tenants..."
TENANTS_RESPONSE=$(curl -s "$API_URL/tenants" \
  -H "Authorization: Bearer $INITIAL_TOKEN")

echo "   Available tenants:"
echo "$TENANTS_RESPONSE" | jq '.items[] | {id, name, is_active}'
echo ""

# Step 4: Switch to tenant 1
echo "4. Switching to tenant 1..."
SWITCH_RESPONSE=$(curl -s -X POST "$API_URL/auth/switch-tenant" \
  -H "Authorization: Bearer $INITIAL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": 1}')

NEW_TOKEN=$(echo $SWITCH_RESPONSE | jq -r '.access_token')

if [ "$NEW_TOKEN" == "null" ] || [ -z "$NEW_TOKEN" ]; then
  echo "   ✗ Failed to switch tenant!"
  echo "   Response:"
  echo "$SWITCH_RESPONSE" | jq '.'
  exit 1
fi

echo "   ✓ Received new token"
echo ""

# Step 5: Decode new JWT
echo "5. Decoding new JWT..."
NEW_B64=$(echo $NEW_TOKEN | cut -d'.' -f2)
NEW_B64_PADDED=$(echo "$NEW_B64" | awk '{while (length($0) % 4 != 0) $0 = $0 "="; print}')
NEW_PAYLOAD=$(echo "$NEW_B64_PADDED" | base64 -d 2>/dev/null || echo "$NEW_B64_PADDED" | base64 -D 2>/dev/null)
NEW_TENANT_ID=$(echo "$NEW_PAYLOAD" | jq -r '.tenant_id')

echo "   New tenant_id: $NEW_TENANT_ID"
echo "   Full payload:"
echo "$NEW_PAYLOAD" | jq '.'
echo ""

# Step 6: Verify tenant_id changed
if [ "$NEW_TENANT_ID" == "1" ]; then
  echo "   ✓ Tenant switch successful! tenant_id is now 1"
else
  echo "   ✗ Tenant switch failed! tenant_id is $NEW_TENANT_ID (expected 1)"
  exit 1
fi
echo ""

# Step 7: Verify data filtering
echo "6. Verifying data filtering..."
LEARNERS_RESPONSE=$(curl -s "$API_URL/learners" \
  -H "Authorization: Bearer $NEW_TOKEN")

LEARNER_COUNT=$(echo $LEARNERS_RESPONSE | jq '.items | length')
TENANT_IDS=$(echo $LEARNERS_RESPONSE | jq -r '.items[].tenant_id' | sort -u)

echo "   Found $LEARNER_COUNT learners"
echo "   Tenant IDs in results: $TENANT_IDS"

if [ "$TENANT_IDS" == "1" ]; then
  echo "   ✓ Data correctly filtered to tenant 1"
else
  echo "   ✗ Data filtering issue! Found tenant IDs: $TENANT_IDS"
  exit 1
fi
echo ""

# Step 8: Switch back to global view
echo "7. Switching back to global view..."
GLOBAL_RESPONSE=$(curl -s -X POST "$API_URL/auth/switch-tenant" \
  -H "Authorization: Bearer $NEW_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": null}')

GLOBAL_TOKEN=$(echo $GLOBAL_RESPONSE | jq -r '.access_token')
GLOBAL_B64=$(echo $GLOBAL_TOKEN | cut -d'.' -f2)
GLOBAL_B64_PADDED=$(echo "$GLOBAL_B64" | awk '{while (length($0) % 4 != 0) $0 = $0 "="; print}')
GLOBAL_PAYLOAD=$(echo "$GLOBAL_B64_PADDED" | base64 -d 2>/dev/null || echo "$GLOBAL_B64_PADDED" | base64 -D 2>/dev/null)
GLOBAL_TENANT_ID=$(echo "$GLOBAL_PAYLOAD" | jq -r '.tenant_id')

echo "   Global tenant_id: $GLOBAL_TENANT_ID"

if [ "$GLOBAL_TENANT_ID" == "null" ]; then
  echo "   ✓ Switched back to global view"
else
  echo "   ✗ Failed to switch to global view! tenant_id is $GLOBAL_TENANT_ID"
  exit 1
fi
echo ""

# Step 9: Verify global data access
echo "8. Verifying global data access..."
GLOBAL_LEARNERS=$(curl -s "$API_URL/learners" \
  -H "Authorization: Bearer $GLOBAL_TOKEN")

GLOBAL_COUNT=$(echo $GLOBAL_LEARNERS | jq '.items | length')
GLOBAL_TENANT_IDS=$(echo $GLOBAL_LEARNERS | jq -r '.items[].tenant_id' | sort -u | tr '\n' ' ')

echo "   Found $GLOBAL_COUNT learners"
echo "   Tenant IDs in results: $GLOBAL_TENANT_IDS"

if [ $GLOBAL_COUNT -gt $LEARNER_COUNT ]; then
  echo "   ✓ Global view shows more data than tenant-specific view"
else
  echo "   ⚠ Warning: Global view has same or less data than tenant view"
fi
echo ""

echo "========================================="
echo "✓ All tests passed!"
echo "========================================="
echo ""
echo "Summary:"
echo "  • Initial tenant_id: $INITIAL_TENANT_ID"
echo "  • After switch to tenant 1: $NEW_TENANT_ID"
echo "  • After switch to global: $GLOBAL_TENANT_ID"
echo "  • Tenant 1 learners: $LEARNER_COUNT"
echo "  • Global learners: $GLOBAL_COUNT"
echo ""
echo "Tokens for manual testing:"
echo "  Initial: $INITIAL_TOKEN"
echo "  Tenant 1: $NEW_TOKEN"
echo "  Global: $GLOBAL_TOKEN"
