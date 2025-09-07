#!/usr/bin/env bash
set -euo pipefail

# Inputs via env:
#   AGENT_ID, AGENT_ALIAS_ID, PROMPT, AWS_REGION (optional)

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI not found. Please setup aws cli first." >&2
  exit 1
fi

: "${AGENT_ID?AGENT_ID is required}"
: "${AGENT_ALIAS_ID?AGENT_ALIAS_ID is required}"
: "${PROMPT?PROMPT is required}"

REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
SESSION_ID="${GITHUB_RUN_ID:-manual}-${RANDOM}"

OUT_JSON="bedrock_agent_output.json"
OUT_TEXT="bedrock_agent_text.txt"

echo "Invoking Bedrock Agent: ${AGENT_ID} alias ${AGENT_ALIAS_ID} in ${REGION}" >&2

aws bedrock-agent-runtime invoke-agent \
  --agent-id "${AGENT_ID}" \
  --agent-alias-id "${AGENT_ALIAS_ID}" \
  --session-id "${SESSION_ID}" \
  --input-text "${PROMPT}" \
  --region "${REGION}" \
  --output json > "${OUT_JSON}"

# Try to extract streamed text chunks if present
if command -v jq >/dev/null 2>&1; then
  # Many Agent responses stream as an array at .responseStream with entries having .chunk.bytes (base64)
  if jq -e '.responseStream' "${OUT_JSON}" >/dev/null 2>&1; then
    jq -r '.responseStream[]? | select(.chunk != null) | .chunk.bytes' "${OUT_JSON}" | base64 --decode > "${OUT_TEXT}" || true
  else
    # Fallback: dump the whole JSON
    jq -r '.' "${OUT_JSON}" > "${OUT_TEXT}"
  fi
else
  cp "${OUT_JSON}" "${OUT_TEXT}"
fi

echo "Saved raw JSON to ${OUT_JSON} and text to ${OUT_TEXT}" >&2

