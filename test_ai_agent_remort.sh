#!/bin/bash

# Configuration
PROJECT_ID="vector-search-poc"
LOCATION="us-central1"
ENGINE_ID="3749695290530070528"  # Update with new ID from deployment_metadata.json
USER_ID="robin@cloudroaster.com"
BASE_URL="https://$LOCATION-aiplatform.googleapis.com/v1beta1/projects/$PROJECT_ID/locations/$LOCATION/reasoningEngines/$ENGINE_ID"
SESSION_ENDPOINT="$BASE_URL/sessions"
QUERY_ENDPOINT="$BASE_URL:query"
STREAM_QUERY_ENDPOINT="$BASE_URL:streamQuery?alt=sse"
OPERATION_ENDPOINT="https://$LOCATION-aiplatform.googleapis.com/v1beta1"

# Get access token
ACCESS_TOKEN=$(gcloud auth print-access-token)

if [ -z "$ACCESS_TOKEN" ]; then
  echo "Error: Failed to get access token. Run 'gcloud auth login' or check gcloud configuration."
  exit 1
fi

# Create a session and extract operation name
SESSION_RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"$USER_ID\"}" \
  "$SESSION_ENDPOINT")

# Log the raw session response
echo "Session Response: $SESSION_RESPONSE"

# Extract operation name
OPERATION_NAME=$(echo "$SESSION_RESPONSE" | jq -r '.name // ""')

if [ -z "$OPERATION_NAME" ]; then
  echo "Warning: No operation name returned; proceeding without session_id"
  SESSION_ID=""
else
  # Extract session_id from operation name (e.g., sessions/8510064418090909696/operations/...)
  SESSION_ID=$(echo "$OPERATION_NAME" | grep -oP 'sessions/\K[^/]+')
  if [ -z "$SESSION_ID" ]; then
    # Poll operation status (max 10 attempts, 2s delay)
    for i in {1..10}; do
      OPERATION_STATUS=$(curl -s -X GET \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        "$OPERATION_ENDPOINT/$OPERATION_NAME")
      echo "Operation Status: $OPERATION_STATUS"
      DONE=$(echo "$OPERATION_STATUS" | jq -r '.done // false')
      if [ "$DONE" = "true" ]; then
        SESSION_ID=$(echo "$OPERATION_STATUS" | jq -r '.response.session_id // .response.id // ""')
        break
      fi
      sleep 2
    done
  fi
fi

if [ -n "$SESSION_ID" ]; then
  echo "Created session with ID: $SESSION_ID"
else
  echo "Warning: Failed to retrieve session_id; proceeding without session_id"
  SESSION_ID=""
fi

# Payload templates (aligned with documentation)
if [ -n "$SESSION_ID" ]; then
  PAYLOAD_CONTENTS='{"contents":[{"parts":[{"text":"%s"}],"role":"user"}],"session_id":"'$SESSION_ID'"}'
else
  PAYLOAD_CONTENTS='{"contents":[{"parts":[{"text":"%s"}],"role":"user"}]}'
fi
# Fallback payload (simplified query)
PAYLOAD_QUERY='{"query":"%s"}'

# Function to try queries with fallbacks
try_query() {
  local endpoint=$1
  local query=$2
  echo "Running query: $query on $endpoint"
  # Try contents payload
  RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$(printf "$PAYLOAD_CONTENTS" "$query")" \
    "$endpoint")
  echo "$RESPONSE"
  # Check for error in response
  if echo "$RESPONSE" | grep -q '"error"'; then
    echo "Contents payload failed. Trying query payload..."
    curl -s -X POST \
      -H "Authorization: Bearer $ACCESS_TOKEN" \
      -H "Content-Type: application/json" \
      -d "$(printf "$PAYLOAD_QUERY" "$query")" \
      "$endpoint"
  fi
}

# Weather query (non-streaming)
try_query "$QUERY_ENDPOINT" "What is the weather in San Francisco?"

# Separator
echo -e "\n---\n"

# Weather query (streaming)
try_query "$STREAM_QUERY_ENDPOINT" "What is the weather in San Francisco?"

# Separator
echo -e "\n---\n"

# Time query (streaming)
try_query "$STREAM_QUERY_ENDPOINT" "What is the current time in San Francisco?"