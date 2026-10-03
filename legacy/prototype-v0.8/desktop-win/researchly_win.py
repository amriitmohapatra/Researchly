#!/usr/bin/env python3
"""Researchly for Windows — scaffold (UNTESTED: no Windows machine has run
this yet; expect a joint debugging session like macOS D1 needed).

Mirrors the macOS D1 design with Windows-native pieces:

    Ctrl+Shift+R — Check selection   (any app)
    Ctrl+Shift+P — Polish selection

Selection capture: simulate Ctrl+C via the `keyboard` library, read the
clipboard with `pyperclip`, restore it afterwards. Panel: a `pywebview`
window rendering the same panel_html as the Mac app. Replace: clipboard +
Ctrl+V paste-back.

Run:    pip install -r requirements-win.txt
        python researchly_win.py
Build:  build_win.bat  (PyInstaller → dist/Researchly.exe)

Known design notes for the future debugging session:
- `keyboard` needs no admin for hotkeys in most setups, but some
  environments require running as Administrator.
- pywebview needs Edge WebView2 runtime (preinstalled on Win 11).
- Clipboard timing constants (SLEEP_*) will likely need tuning per machine.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))                    # researchly pkg
sys.path.insert(0, str(HERE.parent / "desktop-mac"))    # panel_html reuse

import panel_html  # noqa: E402

try:
    import keyboard   # global hotkeys + key simulation
    import pyperclip  # clipboard
    import webview    # pywebview panel
except ImportError as e:  # pragma: no cover
    print("Researchly for Windows needs its dependencies:\n"
          "    pip install -r requirements-win.txt\n"
          f"(import failed: {e})")
    sys.exit(1)

SLEEP_AFTER_COPY = 0.25
SLEEP_BEFORE_PASTE = 0.15


class Engine:
    def __init__(self):
        self.nlp = None
        self.error = None
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            from researchly import api
            self.nlp = api.get_nlp()
            from researchly import rules_lexical, rules_syntax  # noqa: F401
            from researchly import rules_spelling, rules_grammar  # noqa: F401
            print("engine ready")
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"

    def check_html(self, text: str) -> str:
        from researchly import api
        a = api.analyze(text, kind="plain", nlp=self.nlp)
        return panel_html.render_check(
            [s.to_dict() for s in a.suggestions], a.metrics,
            a.hidden_preferences, health=a.health)

    def polish(self, text: str):
        from researchly.transform import polish
        from researchly import config as config_mod
        return polish(text, self.nlp, kind="plain",
                      disabled=config_mod.load().disabled)


ENGINE = Engine()
PENDING = {"polish": None}
WINDOW = None


def capture_selection() -> str:
    old = None
    try:
        old = pyperclip.paste()
    except Exception:
        pass
    keyboard.send("ctrl+c")
    time.sleep(SLEEP_AFTER_COPY)
    try:
        text = pyperclip.paste()
    except Exception:
        text = ""
    if old is not None and old != text:
        # restore the user's clipboard after we've read the selection
        def restore():
            time.sleep(0.3)
            try:
                pyperclip.copy(old)
            except Exception:
                pass
        threading.Thread(target=restore, daemon=True).start()
    return text or ""


def paste_replacement(text: str):
    try:
        pyperclip.copy(text)
        time.sleep(SLEEP_BEFORE_PASTE)
        keyboard.send("ctrl+v")
    except Exception:
        pass


def show_html(html: str):
    global WINDOW
    if WINDOW is None:
        return
    WINDOW.load_html(html)
    WINDOW.show()


def on_check():
    text = capture_selection()
    if not text.strip():
        show_html(panel_html.render_message(
            "No selection", "Select text in any app, then press "
            "Ctrl+Shift+R (check) or Ctrl+Shift+P (polish)."))
        return
    if ENGINE.nlp is None:
        show_html(panel_html.render_message(
            "Warming up", ENGINE.error or "Language model still loading — "
            "try again in a few seconds."))
        return
    threading.Thread(
        target=lambda: show_html(ENGINE.check_html(text)),
        daemon=True).start()


def on_polish():
    text = capture_selection()
    if not text.strip() or ENGINE.nlp is None:
        on_check()
        return

    def work():
        result = ENGINE.polish(text)
        PENDING["polish"] = result
        show_html(panel_html.render_polish(result))
    threading.Thread(target=work, daemon=True).start()


class JsApi:
    """Exposed to the pywebview panel for the two polish buttons."""

    def replace_selection(self):
        r = PENDING.get("polish")
        if r is not None and r.changed:
            WINDOW.hide()
            time.sleep(0.2)          # let focus return to the target app
            paste_replacement(r.rewritten)

    def copy_rewrite(self):
        r = PENDING.get("polish")
        if r is not None:
            pyperclip.copy(r.rewritten)


def main():
    global WINDOW
    keyboard.add_hotkey("ctrl+shift+r", on_check)
    keyboard.add_hotkey("ctrl+shift+p", on_polish)
    WINDOW = webview.create_window(
        "Researchly", html=panel_html.render_message(
            "Researchly is running",
            "Ctrl+Shift+R checks the current selection anywhere; "
            "Ctrl+Shift+P polishes it. Keep this window minimized."),
        width=460, height=620, on_top=True, js_api=JsApi())
    print("Researchly (Windows) running — Ctrl+Shift+R / Ctrl+Shift+P")
    webview.start()


if __name__ == "__main__":
    main()
