#!/usr/bin/env python3
import os
import sys
import json
import time
from typing import List

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError, UnknownServiceError
except Exception as e:
    print(f"boto3 import error: {e}", file=sys.stderr)
    sys.exit(2)


def getenv_required(name: str) -> str:
    v = os.getenv(name)
    if not v:
        print(f"Missing required env: {name}", file=sys.stderr)
        sys.exit(2)
    return v


def invoke_agent(prompt: str, region: str, agent_id: str, agent_alias_id: str):
    client = boto3.client("bedrock-agent-runtime", region_name=region)
    session_id = f"{os.getenv('GITHUB_RUN_ID', 'manual')}-{int(time.time())}"
    resp = client.invoke_agent(
        agentId=agent_id,
        agentAliasId=agent_alias_id,
        sessionId=session_id,
        inputText=prompt,
    )
    # Collect stream text
    parts: List[str] = []
    stream = resp.get("responseStream")
    if stream is None:
        # Some SDKs may return 'completion' or other fields; fallback to json dump
        return json.dumps(resp, ensure_ascii=False), ""
    for event in stream:
        if "chunk" in event:
            b = event["chunk"].get("bytes", b"")
            if isinstance(b, (bytes, bytearray)):
                parts.append(b.decode("utf-8", errors="ignore"))
            else:
                try:
                    import base64
                    parts.append(base64.b64decode(b).decode("utf-8", errors="ignore"))
                except Exception:
                    parts.append(str(b))
    text = "".join(parts)
    # We can't JSON-serialize the streaming object directly; return text only
    return None, text


def invoke_model(prompt: str, region: str, model_id: str):
    client = boto3.client("bedrock-runtime", region_name=region)
    body = {
        "inputText": prompt,
        "textGenerationConfig": {
            "maxTokenCount": 2048,
            "temperature": 0.3,
            "topP": 0.9,
        },
    }
    resp = client.invoke_model(
        modelId=model_id,
        body=json.dumps(body).encode("utf-8"),
        accept="application/json",
        contentType="application/json",
    )
    payload = resp.get("body")
    if hasattr(payload, "read"):
        raw = payload.read()
    else:
        raw = payload or b""
    try:
        data = json.loads(raw.decode("utf-8", errors="ignore"))
    except Exception:
        # Return raw string if JSON parsing fails
        return raw.decode("utf-8", errors="ignore")

    # Try common output shapes
    txt = None
    if isinstance(data, dict):
        if "results" in data and isinstance(data["results"], list) and data["results"]:
            r0 = data["results"][0]
            txt = r0.get("outputText") or r0.get("text")
        if not txt and "generation" in data:
            txt = data.get("generation")
        if not txt and "output" in data:
            txt = data.get("output")
        if not txt and "completions" in data:
            comps = data.get("completions")
            if isinstance(comps, list) and comps:
                txt = comps[0]
        if not txt and "content" in data:
            # anthropic-like format may be nested; do a simple flatten
            if isinstance(data["content"], list):
                chunks = []
                for c in data["content"]:
                    if isinstance(c, dict) and c.get("type") == "text":
                        chunks.append(c.get("text") or "")
                if chunks:
                    txt = "".join(chunks)
    return txt or json.dumps(data, ensure_ascii=False)


def main():
    prompt = getenv_required("PROMPT")
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
    agent_id = os.getenv("AGENT_ID")
    agent_alias_id = os.getenv("AGENT_ALIAS_ID")
    model_id = os.getenv("MODEL_ID", "amazon.titan-text-premier-v1:0")

    out_json_path = "bedrock_agent_output.json"
    out_text_path = "bedrock_agent_text.txt"

    text = None
    json_dump = None

    # Prefer agent if parameters available; otherwise go straight to model
    if agent_id and agent_alias_id:
        try:
            json_dump, text = invoke_agent(prompt, region, agent_id, agent_alias_id)
        except (UnknownServiceError, ClientError, BotoCoreError, Exception) as e:
            sys.stderr.write(f"invoke_agent failed: {e}\nFalling back to invoke_model...\n")
            text = None

    if text is None:
        text = invoke_model(prompt, region, model_id)

    # Persist outputs
    try:
        if json_dump is None:
            json_dump = json.dumps({"note": "Agent stream not serialized; see text file."}, ensure_ascii=False)
        with open(out_json_path, "w", encoding="utf-8") as f:
            f.write(json_dump)
    except Exception as e:
        sys.stderr.write(f"Failed to write JSON output: {e}\n")

    try:
        with open(out_text_path, "w", encoding="utf-8") as f:
            f.write(text or "")
    except Exception as e:
        sys.stderr.write(f"Failed to write text output: {e}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())

