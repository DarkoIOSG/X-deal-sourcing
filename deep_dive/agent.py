"""Deep-dive agent. Given project + thesis + phase 2 scoring, produces a memo."""
import json
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from shared.ic_retrieval import retrieve_ic_context

load_dotenv()

client = Anthropic()
MODEL = "claude-opus-4-7"
SYSTEM_PROMPT = Path("shared/prompts/agent_system.txt").read_text()
LOG_DIR = Path("data/agent_logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

TOOLS = [
    {"type": "web_search_20250305", "name": "web_search", "max_uses": 8},
    {"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": 5},
    {
        "name": "retrieve_ic_context",
        "description": (
            "Search past IC meeting transcripts and published research for prior "
            "discussions of similar projects, sectors, or patterns. Returns top-k "
            "matching chunks with source file and date."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query describing what past context you want.",
                },
                "top_k": {"type": "integer", "default": 4},
            },
            "required": ["query"],
        },
    },
]


def render_user_message(project, thesis_doc, phase2_json):
    tweets = "\n".join(f"- {t}" for t in project.get("tweets", []))
    return f"""# Active fund thesis

{thesis_doc}

# Phase 2 rubric scoring (initial take to confirm or refute)

```json
{json.dumps(phase2_json, indent=2, ensure_ascii=False)}
```

# Project

- X handle: {project['handle']}
- Description: {project.get('description', '(none)')}
- Categories: {', '.join(project.get('categories', []))}

## Recent tweets
{tweets}

Now investigate and produce the memo.
"""


def _serialize_block(block):
    if isinstance(block, dict):
        return block
    if hasattr(block, "model_dump"):
        return block.model_dump()
    return str(block)


def deep_dive(project, thesis_doc, phase2_json, max_iters=15):
    """Run the agent loop. Returns {memo, trace, iters}."""
    user_msg = render_user_message(project, thesis_doc, phase2_json)
    messages = [{"role": "user", "content": user_msg}]

    for iter_num in range(1, max_iters + 1):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason == "end_turn":
            memo = "".join(
                getattr(b, "text", "") for b in resp.content
                if getattr(b, "type", None) == "text"
            )
            return {"memo": memo, "trace": messages, "iters": iter_num}

        if resp.stop_reason == "tool_use":
            tool_results = []
            for block in resp.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                # web_search and web_fetch are server-side; they don't reach this branch
                if block.name == "retrieve_ic_context":
                    try:
                        result = retrieve_ic_context(**block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, ensure_ascii=False),
                        })
                    except Exception as e:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Error: {e}",
                            "is_error": True,
                        })
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            continue

        raise RuntimeError(f"Unexpected stop_reason: {resp.stop_reason}")

    raise RuntimeError(f"Agent exceeded max_iters={max_iters}")


def deep_dive_and_log(project, thesis_doc, phase2_json):
    """Run deep_dive and log the full trace for debugging."""
    handle = project.get("handle", "unknown").lstrip("@").replace("/", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    result = deep_dive(project, thesis_doc, phase2_json)

    serializable_trace = []
    for msg in result["trace"]:
        content = msg["content"]
        if isinstance(content, str):
            serializable_trace.append(msg)
        else:
            serializable_trace.append({
                "role": msg["role"],
                "content": [_serialize_block(b) for b in content],
            })

    log_path = LOG_DIR / f"{ts}_{handle}.json"
    log_path.write_text(json.dumps({
        "handle": project.get("handle"),
        "iters": result["iters"],
        "memo": result["memo"],
        "trace": serializable_trace,
    }, indent=2, ensure_ascii=False, default=str))
    print(f"\n[Trace logged: {log_path}]")
    return result["memo"]
