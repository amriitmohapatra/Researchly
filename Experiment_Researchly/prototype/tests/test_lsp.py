"""Smoke test: drive the LSP server over real stdio JSON-RPC."""

import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Without pygls the server process dies instantly on ImportError. Because the
# test discarded stderr, that surfaced as "no diagnostics published" after a
# 40-second wait — a missing dependency wearing the costume of a broken
# checker. Same failure shape as the grammar tier; name it instead.
requires_pygls = pytest.mark.skipif(
    importlib.util.find_spec("pygls") is None,
    reason="pygls is not installed — `pip install 'pygls<2'` to run the "
           "LSP smoke test")


def _msg(obj) -> bytes:
    body = json.dumps(obj).encode()
    return f"Content-Length: {len(body)}\r\n\r\n".encode() + body


def _read_messages(stream, deadline: float):
    """Read LSP messages until deadline; return list of parsed bodies."""
    out = []
    buf = b""
    stream_fd = stream
    import os
    os.set_blocking(stream_fd.fileno(), False)
    while time.time() < deadline:
        try:
            chunk = stream_fd.read(65536)
        except Exception:
            chunk = None
        if chunk:
            buf += chunk
        else:
            time.sleep(0.05)
        while True:
            sep = buf.find(b"\r\n\r\n")
            if sep == -1:
                break
            headers = buf[:sep].decode(errors="replace")
            length = 0
            for line in headers.split("\r\n"):
                if line.lower().startswith("content-length:"):
                    length = int(line.split(":")[1].strip())
            if len(buf) < sep + 4 + length:
                break
            body = buf[sep + 4:sep + 4 + length]
            buf = buf[sep + 4 + length:]
            try:
                out.append(json.loads(body))
            except json.JSONDecodeError:
                pass
    return out


@requires_pygls
def test_lsp_publishes_diagnostics_and_quickfix_data():
    proc = subprocess.Popen(
        [sys.executable, "-m", "researchly.lsp"],
        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    try:
        uri = "file:///tmp/researchly-lsp-test.qmd"
        text = ("# Discussion\n\n"
                "We utilize diaries in order to measure contacts. "
                "This proves that stratification matters.\n")

        proc.stdin.write(_msg({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"processId": None, "rootUri": "file:///tmp",
                       "capabilities": {}}}))
        proc.stdin.write(_msg({
            "jsonrpc": "2.0", "method": "initialized", "params": {}}))
        proc.stdin.write(_msg({
            "jsonrpc": "2.0", "method": "textDocument/didOpen",
            "params": {"textDocument": {
                "uri": uri, "languageId": "markdown", "version": 1,
                "text": text}}}))
        proc.stdin.flush()

        # generous: first check loads the spaCy model
        msgs = _read_messages(proc.stdout, time.time() + 40)
        pubs = [m for m in msgs
                if m.get("method") == "textDocument/publishDiagnostics"
                and m["params"]["uri"] == uri
                and m["params"]["diagnostics"]]
        if not pubs:
            # If the server died, its traceback is the real message.
            proc.poll()
            stderr = b""
            if proc.returncode is not None:
                try:
                    stderr = proc.stderr.read() or b""
                except Exception:
                    pass
            raise AssertionError(
                f"no diagnostics published; got methods: "
                f"{[m.get('method') or m.get('id') for m in msgs]}"
                + (f"\nserver exited {proc.returncode}:\n"
                   f"{stderr.decode(errors='replace')}" if stderr else ""))

        diags = pubs[-1]["params"]["diagnostics"]
        codes = {d["code"] for d in diags}
        assert "W201" in codes         # utilize
        assert "W202" in codes         # in order to
        assert "C302" in codes         # proves, in Discussion section
        w201 = next(d for d in diags if d["code"] == "W201")
        assert w201["source"] == "researchly"
        assert w201["data"]["replacement"] == "use"
        # range points at 'utilize' on line 2 (0-based)
        assert w201["range"]["start"]["line"] == 2
    finally:
        proc.kill()
