#!/usr/bin/env python3
"""
start_all_cloud.py - Production 24/7 Cloud Orchestrator
Runs both the Web Demo Server (demo_server.py) and the Voice Agent Worker (agent.py start)
concurrently with automatic restart and graceful shutdown handling.
Perfect for single-container cloud hosting on Railway, Render, Fly.io, or VPS.
"""

import os
import signal
import subprocess
import sys
import time

processes = []


def signal_handler(sig, frame):
    print("\n[ORCHESTRATOR] Shutting down services gracefully...")
    for p in processes:
        if p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def main():
    python_cmd = sys.executable

    print("=" * 65)
    print(" [ARIA 24/7 VOICE AI] - CLOUD PRODUCTION SUPERVISOR")
    print("=" * 65)

    # 1. Start LiveKit Voice Agent Worker in production mode
    print("[1/2] Launching Voice Agent Worker (agent.py start)...")
    agent_proc = subprocess.Popen(
        [python_cmd, "agent.py", "start"],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    processes.append(agent_proc)

    # 2. Start Demo & WebRTC Token Server
    print("[2/2] Launching Web Demo & Token Server (demo_server.py)...")
    server_proc = subprocess.Popen(
        [python_cmd, "demo_server.py"],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    processes.append(server_proc)

    print("[SUCCESS] Both services running 24/7 in cloud environment.")
    print("=" * 65)

    # Monitor both processes
    while True:
        time.sleep(2)
        for p in processes:
            ret = p.poll()
            if ret is not None:
                print(f"[WARNING] Process {p.args} exited with code {ret}. Shutting down supervisor.")
                signal_handler(None, None)


if __name__ == "__main__":
    main()
