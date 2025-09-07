#!/usr/bin/env python3
import os
import sys
import json
import time
import traceback
from typing import List

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
    if DEBUG:
        try:
            keys = list(resp.keys())
            log(f"invoke_agent: response keys={keys}")
            for k in keys:
                v = resp.get(k)
                log(f"invoke_agent: key={k} type={type(v)}")
        except Exception as e:
            log(f"invoke_agent: failed to introspect response: {e}")
    # Some SDKs expose the stream under 'completion' instead of 'responseStream'
    stream = resp.get("responseStream") or resp.get("completion")
    if stream is None:
        if DEBUG:
            log("invoke_agent: responseStream is None (no streaming content)")
        # Agent responded without a stream; return a small JSON note and human text
        keys = []
        try:
            keys = list(resp.keys())
        except Exception:
            pass
        json_note = json.dumps({"note": "Agent returned no stream", "response_keys": keys}, ensure_ascii=False)
        text_note = (
            "Agentのレスポンスにストリームがありませんでした。"
            f" response_keys={keys}"
        )
        return json_note, text_note
    chunk_count = 0
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
            chunk_count += 1
        else:
            if DEBUG:
                try:
                    log(f"invoke_agent: non-chunk event keys={list(event.keys())}")
                except Exception:
                    pass
    text = "".join(parts)
    if DEBUG:
        log(f"invoke_agent: received stream chunks={chunk_count} text_len={len(text)}")
    # We can't JSON-serialize the streaming object directly; return text only
    return None, text


# invoke_model および関連の自動モデル解決は不要のため削除


def main():
    prompt = getenv_required("PROMPT")
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
    agent_id = os.getenv("AGENT_ID")
    agent_alias_id = os.getenv("AGENT_ALIAS_ID")

    out_json_path = "bedrock_agent_output.json"
    out_text_path = "bedrock_agent_text.txt"

    text = None
    json_dump = None

    if DEBUG:
        try:
            sts = boto3.client("sts", region_name=region)
            ident = sts.get_caller_identity()
            log(f"env: region={region} agent_id={agent_id} alias={agent_alias_id}")
            log(f"sts: account={ident.get('Account')} arn={ident.get('Arn')}")
            log(f"prompt: len={len(prompt)} preview={prompt[:200].replace('\n',' ')}")
        except Exception as e:
            log(f"sts/getenv debug failed: {e}")

    # Prefer agent; モデル呼び出しへのフォールバックは行わない
    if agent_id and agent_alias_id:
        try:
            json_dump, text = invoke_agent(prompt, region, agent_id, agent_alias_id)
        except (UnknownServiceError, ClientError, BotoCoreError, Exception) as e:
            log(f"invoke_agent failed: {e}\n{traceback.format_exc()}")
            # Produce human-friendly error text and JSON dump; do not fallback
            text = f"Agent呼び出しに失敗しました。{e}\n詳細はログを確認してください。"
            json_dump = json.dumps({"error": str(e), "trace": traceback.format_exc()}, ensure_ascii=False)
    else:
        text = "AGENT_ID/AGENT_ALIAS_ID が未設定のため、Agent呼び出しを実行しませんでした。"
        json_dump = json.dumps({"error": "missing agent parameters"}, ensure_ascii=False)

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
