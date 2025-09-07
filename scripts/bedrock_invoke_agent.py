#!/usr/bin/env python3
import os
import sys
import json
import time
import traceback
from typing import List

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import BotoCoreError, ClientError, UnknownServiceError, EventStreamError
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


def resolve_prompt() -> str:
    """Resolve prompt from PROMPT_FILE (if set or default exists) else PROMPT env.

    - If env PROMPT_FILE is set, read that file.
    - Else if default file scripts/prompts/pr_improve_agent_ja.md exists, use it.
    - Else fallback to PROMPT env (required).
    """
    # 1) Explicit file via env
    pfile = os.getenv("PROMPT_FILE")
    if pfile and os.path.isfile(pfile):
        if DEBUG:
            log(f"resolve_prompt: using PROMPT_FILE={pfile}")
        with open(pfile, "r", encoding="utf-8") as f:
            return f.read()
    # 2) Default repo file
    default_file = os.path.join("scripts", "prompts", "pr_improve_agent_ja.md")
    if os.path.isfile(default_file):
        if DEBUG:
            log(f"resolve_prompt: using default prompt file={default_file}")
        with open(default_file, "r", encoding="utf-8") as f:
            return f.read()
    # 3) Fallback to PROMPT env
    if DEBUG:
        log("resolve_prompt: falling back to PROMPT env")
    return getenv_required("PROMPT")


def append_repo_context(prompt_text: str) -> str:
    owner = os.getenv("REPO_OWNER")
    name = os.getenv("REPO_NAME")
    full = os.getenv("REPO_FULL")
    pr_number = os.getenv("PR_NUMBER")
    pr_url = os.getenv("PR_URL")
    head_ref = os.getenv("HEAD_REF")
    base_ref = os.getenv("BASE_REF")
    head_sha = os.getenv("HEAD_SHA")

    # Derive owner/name from full if missing
    if (not owner or not name) and full and "/" in full:
        parts = full.split("/", 1)
        owner = owner or parts[0]
        name = name or parts[1]

    if DEBUG:
        log(
            f"append_repo_context: owner={owner} name={name} pr={pr_number} head_ref={head_ref} base_ref={base_ref} sha={head_sha} url={pr_url}"
        )

    lines = []
    if owner or name or pr_number or head_ref or base_ref or head_sha or pr_url:
        lines.append("\n### 対象リポジトリ情報")
        if owner or name:
            repo_disp = f"{owner or '(unknown)'}/{name or '(unknown)'}"
            lines.append(f"- 組織/リポジトリ: {repo_disp}")
        if pr_number:
            lines.append(f"- PR番号: {pr_number}")
        if pr_url:
            lines.append(f"- PR URL: {pr_url}")
        if head_ref and base_ref:
            lines.append(f"- ブランチ: {head_ref} → {base_ref}")
        elif head_ref:
            lines.append(f"- ブランチ: {head_ref}")
        if head_sha:
            lines.append(f"- HEAD SHA: {head_sha}")

    return prompt_text + ("\n" + "\n".join(lines) if lines else "")


def make_session(region: str):
    """Create a boto3 Session, honoring profile env vars for local runs.

    Priority:
      1. BEDROCK_AWS_PROFILE
      2. AWS_PROFILE
      3. Default credentials chain
    """
    profile = os.getenv("BEDROCK_AWS_PROFILE") or os.getenv("AWS_PROFILE")
    if profile:
        if DEBUG:
            log(f"make_session: using profile={profile} region={region}")
        return boto3.Session(profile_name=profile, region_name=region)
    if DEBUG:
        log(f"make_session: using default credentials chain region={region}")
    return boto3.Session(region_name=region)


def make_config() -> Config:
    """Build botocore Config with extended timeouts and retries.

    Env overrides:
      - BEDROCK_CONNECT_TIMEOUT (sec, default 10)
      - BEDROCK_READ_TIMEOUT    (sec, default 1800 = 30min)
      - BEDROCK_MAX_ATTEMPTS    (default 3)
      - BEDROCK_RETRY_MODE      (default 'standard')
    """
    ct = int(os.getenv("BEDROCK_CONNECT_TIMEOUT", "10"))
    rt = int(os.getenv("BEDROCK_READ_TIMEOUT", "1800"))
    ma = int(os.getenv("BEDROCK_MAX_ATTEMPTS", "3"))
    mode = os.getenv("BEDROCK_RETRY_MODE", "standard")
    if DEBUG:
        log(f"make_config: connect_timeout={ct}s read_timeout={rt}s max_attempts={ma} mode={mode}")
    return Config(connect_timeout=ct, read_timeout=rt, retries={"max_attempts": ma, "mode": mode})


def make_client(session: boto3.Session, service_name: str):
    return session.client(service_name, config=make_config())


def invoke_agent(prompt: str, region: str, agent_id: str, agent_alias_id: str):
    session = make_session(region)
    client = make_client(session, "bedrock-agent-runtime")
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
    non_chunk_notes: List[str] = []
    try:
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
                # Keep a short note for non-chunk events to aid debugging
                try:
                    keys = list(event.keys())
                except Exception:
                    keys = []
                note = f"[non-chunk event] keys={keys}"
                non_chunk_notes.append(note)
                if DEBUG:
                    log(f"invoke_agent: {note}")
    except EventStreamError as ese:
        # Surface partial content and error details
        if DEBUG:
            log(f"invoke_agent: EventStreamError: {ese}")
        text_partial = "".join(parts).strip()
        err_msg = (
            (text_partial + "\n\n" if text_partial else "") +
            f"Agentのストリーム処理でエラーが発生しました: {ese}. 後で再試行してください。"
        )
        json_err = json.dumps({
            "error": "EventStreamError",
            "message": str(ese),
            "non_chunk_events": non_chunk_notes,
        }, ensure_ascii=False)
        return json_err, err_msg
    text = "".join(parts)
    if DEBUG:
        log(f"invoke_agent: received stream chunks={chunk_count} text_len={len(text)}")
    # We can't JSON-serialize the streaming object directly; return text only
    return None, text


# invoke_model および関連の自動モデル解決は不要のため削除


def main():
    prompt = resolve_prompt()
    prompt = append_repo_context(prompt)
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
    agent_id = os.getenv("AGENT_ID")
    agent_alias_id = os.getenv("AGENT_ALIAS_ID")

    out_json_path = "bedrock_agent_output.json"
    out_text_path = "bedrock_agent_text.txt"

    text = None
    json_dump = None

    if DEBUG:
        try:
            session = make_session(region)
            sts = make_client(session, "sts")
            ident = sts.get_caller_identity()
            profile = os.getenv("BEDROCK_AWS_PROFILE") or os.getenv("AWS_PROFILE") or "(default)"
            log(f"env: region={region} agent_id={agent_id} alias={agent_alias_id}")
            log(f"profile: {profile}")
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
