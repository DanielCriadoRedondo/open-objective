"""Export public inputs/tool calls/results from local fresh-session rollouts.

Reasoning records and encrypted reasoning are deliberately excluded.
"""
import argparse
import hashlib
import json
import pathlib

def text_blocks(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in text_blocks(item)]
    if isinstance(value, dict):
        return text_blocks(value.get("text", value.get("content", [])))
    return []

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=pathlib.Path)
    parser.add_argument("sessions", type=pathlib.Path)
    parser.add_argument("--rollout-dir", type=pathlib.Path, required=True)
    args = parser.parse_args()
    cases = json.loads(args.manifest.read_text(encoding="utf-8"))["cases"]
    sessions = json.loads(args.sessions.read_text(encoding="utf-8"))["cases"]
    by_variant = {c["variant"]: c for c in cases}
    for session in sessions:
        matches = list(args.rollout_dir.glob(f"*{session['threadId']}*.jsonl"))
        if len(matches) != 1:
            raise RuntimeError(f"Expected one rollout for {session['threadId']}, got {len(matches)}")
        raw = matches[0].read_bytes()
        rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
        contexts, calls, outputs, user_messages, delegated_inputs, finals = [], [], [], [], [], []
        complete = False
        for row in rows:
            kind, payload = row.get("type"), row.get("payload", {})
            if kind == "turn_context":
                contexts.append({key: payload[key] for key in ["model", "effort", "cwd"] if key in payload})
            if kind == "event_msg" and payload.get("type") == "task_complete":
                complete = True
            if kind != "response_item":
                continue
            item_type = payload.get("type")
            if item_type in {"function_call", "custom_tool_call"}:
                calls.append({key: payload[key] for key in ["type", "name", "namespace", "call_id", "input", "arguments"] if key in payload})
            if item_type in {"function_call_output", "custom_tool_call_output"}:
                outputs.append({key: payload[key] for key in ["type", "name", "namespace", "call_id", "output"] if key in payload})
                if payload.get("name") == "create_thread":
                    delegated_inputs.extend(text_blocks(payload.get("output", [])))
            if item_type == "message" and payload.get("role") == "user":
                user_messages.extend(text_blocks(payload.get("content", [])))
            if item_type == "message" and payload.get("role") == "assistant" and payload.get("phase") in {"final", "final_answer"}:
                finals.extend(text_blocks(payload.get("content", [])))
        result = {"threadId": session["threadId"], "source_rollout": str(matches[0]),
                  "source_sha256": hashlib.sha256(raw).hexdigest(), "completed": complete,
                  "contexts": contexts, "user_messages": user_messages, "delegated_inputs": delegated_inputs,
                  "tool_calls": calls, "tool_outputs": outputs, "final_response": "\n".join(finals)}
        target = args.manifest.parent / f"{by_variant[session['variant']]['run']}.tools.json"
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(session["variant"], "completed=" + str(complete), "tool_calls=" + str(len(calls)), "models=" + str(sorted({c.get('model') for c in contexts})))

if __name__ == "__main__":
    main()
