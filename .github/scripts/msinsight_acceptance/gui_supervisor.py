#!/usr/bin/env python3
"""Parameterized NEW derivative of the real supervisor; syntax checked only.
Run in the same network runtime as the browser, after staging reviewed binaries.
Only its own fresh process group is stopped. Use Ctrl-C in this terminal to stop.
"""

import argparse
import functools
import http.server
import json
import os
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    root = args.evidence.resolve()
    stage = root / "server"
    for name in [
        "profiler_server",
        "libmsinsight.so",
        "libsqlite.so",
        "mem_snap_dump/tools/dump2db.py",
    ]:
        if not (stage / name).is_file():
            parser.error("Missing staged file: " + name)
    for name in ["gui-root/index.html", "gui-root/plugins/Leaks/index.html"]:
        if not (root / name).is_file():
            parser.error("Missing production bundle: " + name)
    for name in [
        "server-process.trace",
        "server-console.log",
        "owned-process.json",
        "stop-gui",
    ]:
        if (root / name).exists():
            parser.error("Use a fresh evidence runtime; existing " + name)
    strace = shutil.which("strace")
    if not strace:
        parser.error("strace is required before server startup")
    (root / "home").mkdir(exist_ok=True)
    servers = []
    process = None
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    try:
        # Bind HTTP first, so a busy port cannot leave an orphan C++ server.
        for port, directory in [
            (5174, root / "gui-root"),
            (3007, root / "gui-root/plugins/Leaks"),
        ]:
            srv = http.server.ThreadingHTTPServer(
                ("127.0.0.1", port),
                functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory)),
            )
            servers.append(srv)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
        with (root / "server-console.log").open("x") as log:
            process = subprocess.Popen(
                [
                    strace,
                    "-f",
                    "-tt",
                    "-s",
                    "1000",
                    "-e",
                    "trace=process",
                    "-o",
                    str(root / "server-process.trace"),
                    "./profiler_server",
                    "--wsPort=9000",
                    "--wsHost=127.0.0.1",
                ],
                cwd=stage,
                env=dict(os.environ, LD_LIBRARY_PATH=str(stage), HOME=str(root / "home")),
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            with (root / "owned-process.json").open("x") as record:
                json.dump(
                    {
                        "supervisor_pid": os.getpid(),
                        "strace_process_group": process.pid,
                        "started_epoch": time.time(),
                    },
                    record,
                )
            print(
                "HTTP listening at http://127.0.0.1:5174/; verify server WS readiness before importing.",
                flush=True,
            )
            while not stop.wait(0.5) and not (root / "stop-gui").exists():
                if process.poll() is not None:
                    raise RuntimeError("Server/strace exited: " + str(process.returncode))
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print(
                    "Owned process has not exited; inspect its recorded group. No force kill performed.",
                    flush=True,
                )
        for srv in servers:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    main()
