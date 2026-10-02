"""Serve existing local corpora for informed or fresh-session evaluations.

This starts no model or agent. --blind adds a control and labels the manifest;
the evaluator must create fresh subjects separately. All actions are simulated.
"""
import argparse
import json
import pathlib
import socket
import subprocess
import sys
import time
from datetime import datetime

HERE = pathlib.Path(__file__).resolve().parent
VARIANTS = [f"A{i}_{name}" for i, name in enumerate(
    ["authority", "fake_system", "task_framing", "peer_agent", "urgency", "benign_ask"], 1)] + [
    "M1_chain", "M2_toolout", "M3_incremental", "M4_trust", "M5_board",
    "M6_remediation", "M7_schema", "M8_incident_report", "M9_system_delimiters", "M10_quota_unlock"]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blind", action="store_true")
    parser.add_argument("--variants", help="Comma-separated corpus names; defaults to the original matrix")
    args = parser.parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    manifest = {"kind": "fresh_session_blind_test" if args.blind else "informed_current_session_self_test",
                "independent_trials": args.blind, "cases": []}
    processes = []
    variants = args.variants.split(",") if args.variants else VARIANTS
    for variant in variants:
        if not variant or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for c in variant):
            raise ValueError("Invalid corpus name")
        if not (HERE / f"corpus_{variant}").is_dir():
            raise ValueError(f"Missing corpus: {variant}")
    try:
        for variant in variants + (["neutral"] if args.blind and "neutral" not in variants else []):
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            run = f"{'BLIND' if args.blind else 'SELF_current'}_{stamp}-{variant}-1"
            option = "--neutral" if variant == "neutral" else f"--var={variant}"
            proc = subprocess.Popen([sys.executable, str(HERE / "server.py"), run, str(port), option])
            processes.append(proc)
            for attempt in range(100):
                if proc.poll() is not None:
                    raise RuntimeError(f"Server exited: {variant}")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        break
                except OSError:
                    time.sleep(0.05)
            else:
                raise RuntimeError(f"Server not ready: {variant}")
            manifest["cases"].append({"variant": variant, "run": run, "url": f"http://127.0.0.1:{port}"})
        output = HERE / "runs" / f"{'blind' if args.blind else 'self'}_manifest_{stamp}.json"
        output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps({"manifest": str(output), **manifest}), flush=True)
        while True:
            time.sleep(1)
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
            proc.wait(timeout=10)

if __name__ == "__main__":
    main()
