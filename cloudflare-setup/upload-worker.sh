#!/bin/bash

# Direct worker upload script

source .env

ACCOUNT_ID="9facb8af1cf22a222cd876b841790ddd"
WORKER_NAME="linknode-proxy"

echo "Uploading worker script..."

# Upload using the simple script endpoint
curl -X PUT \
  "https://api.cloudflare.com/client/v4/accounts/${ACCOUNT_ID}/workers/scripts/${WORKER_NAME}" \
  -H "Authorization: Bearer ${CF_API_TOKEN}" \
  -H "Content-Type: application/javascript" \
  --data-binary @worker.js \
  | jq .