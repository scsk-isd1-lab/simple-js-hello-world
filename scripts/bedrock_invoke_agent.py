#!/usr/bin/env python3
import os
import sys
import json
import time
import traceback
from typing import List, Optional

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError, UnknownServiceError
except Exception as e:
    print(f"boto3 import error: {e}", file=sys.stderr)
    sys.exit(2)


DEBUG = os.getenv("DEBUG_BEDROCK", "0") not in ("", "0", "false", "False", "OFF")


def log(msg: str):
    sys.stderr.write(f"[bedrock-debug] {msg}\n")
    sys.stderr.flush()


def getenv_required(name: str) -> str:
    v = os.getenv(name)
    if not v:
        print(f"Missing required env: {name}", file=sys.stderr)
        sys.exit(2)
    return v


def invoke_agent(prompt: str, region: str, agent_id: str, agent_alias_id: str):
    client = boto3.client("bedrock-agent-runtime", region_name=region)
    session_id = f"{os.getenv('GITHUB_RUN_ID', 'manual')}-{int(time.time())}"
    if DEBUG:
        log(f"invoke_agent: region={region} agent_id={agent_id} alias={agent_alias_id} session_id={session_id}")
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
        if DEBUG:
            log("invoke_agent: responseStream is None (no streaming content)")
        # Agent responded without a stream; return empty text (we keep JSON dump separate)
        return None, ""
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
    if DEBUG:
        log(f"invoke_agent: received stream chunks={len(parts)} text_len={len(text)}")
    # We can't JSON-serialize the streaming object directly; return text only
    return None, text


def resolve_model_id(region: str, requested: Optional[str]) -> str:
    """Return a valid model ID for this region. Prefer requested if available; otherwise pick a text generation model."""
    if requested:
        # Validate requested exists in region
        try:
            bedrock = boto3.client("bedrock", region_name=region)
            models = bedrock.list_foundation_models()
            ids = {m.get("modelId") for m in models.get("modelSummaries", [])}
            if requested in ids:
                return requested
            # Some providers version their IDs; accept prefix match
            for mid in ids:
                if mid.startswith(requested):
                    return mid
        except Exception:
            # If enumeration fails, attempt with requested as-is
            return requested
    # Auto-pick first sensible text model
    try:
        bedrock = boto3.client("bedrock", region_name=region)
        models = bedrock.list_foundation_models()
        if DEBUG:
            log(f"resolve_model_id: found {len(models.get('modelSummaries', []))} models in {region}")
        for m in models.get("modelSummaries", []):
            if not isinstance(m, dict):
                continue
            ins = m.get("inferenceTypesSupported") or []
            inputs = m.get("inputModalities") or []
            outputs = m.get("outputModalities") or []
            if "ON_DEMAND" in ins and "TEXT" in inputs and "TEXT" in outputs:
                mid = m.get("modelId")
                if mid:
                    log(f"resolve_model_id: selected model {mid}")
                    return mid
    except Exception as e:
        log(f"resolve_model_id: failed to list models in {region}: {e}")
    # Final fallback to a commonly available Titan text model id (may still fail if not available)
    return requested or "amazon.titan-text-lite-v1"


def invoke_model(prompt: str, region: str, model_id: Optional[str]):
    client = boto3.client("bedrock-runtime", region_name=region)
    model_to_use = resolve_model_id(region, model_id)
    if DEBUG:
        log(f"invoke_model: model_id={model_to_use} region={region}")
    body = {
        "inputText": prompt,
        "textGenerationConfig": {
            "maxTokenCount": 2048,
            "temperature": 0.3,
            "topP": 0.9,
        },
    }
    resp = client.invoke_model(
        modelId=model_to_use,
        body=json.dumps(body).encode("utf-8"),
        accept="application/json",
        contentType="application/json",
    )
    payload = resp.get("body")
    if hasattr(payload, "read"):
        raw = payload.read()
    else:
        raw = payload or b""
    if DEBUG:
        log(f"invoke_model: raw bytes len={len(raw) if raw else 0}")
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

    if DEBUG:
        try:
            sts = boto3.client("sts", region_name=region)
            ident = sts.get_caller_identity()
            log(f"env: region={region} agent_id={agent_id} alias={agent_alias_id} model_id={model_id}")
            log(f"sts: account={ident.get('Account')} arn={ident.get('Arn')}")
            log(f"prompt: len={len(prompt)} preview={prompt[:200].replace('\n',' ')}")
        except Exception as e:
            log(f"sts/getenv debug failed: {e}")

    # Prefer agent if parameters available; otherwise go straight to model
    if agent_id and agent_alias_id:
        try:
            json_dump, text = invoke_agent(prompt, region, agent_id, agent_alias_id)
        except (UnknownServiceError, ClientError, BotoCoreError, Exception) as e:
            log(f"invoke_agent failed: {e}\n{traceback.format_exc()}")
            log("Falling back to invoke_model...")
            text = None

    if text is None:
        text = invoke_model(prompt, region, model_id)

    # Persist outputs
    try:
        if json_dump is None:
            json_dump = json.dumps({"note": "Agent stream not serialized; see text file."}, ensure_ascii=False)
        with open(out_json_path, "w", encoding="utf-8") as f:
            f.write(json_dump)
        if DEBUG:
            log(f"wrote {out_json_path} ({len(json_dump)} chars)")
    except Exception as e:
        log(f"Failed to write JSON output: {e}")

    try:
        if not text or not str(text).strip():
            text = "Bedrockの出力が空でした。詳細は Actions のログおよび bedrock_agent_output.json を確認してください。"
        with open(out_text_path, "w", encoding="utf-8") as f:
            f.write(text or "")
        if DEBUG:
            log(f"wrote {out_text_path} (len={len(text or '')})")
    except Exception as e:
        log(f"Failed to write text output: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
