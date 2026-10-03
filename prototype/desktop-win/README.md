# Researchly for Windows — scaffold (UNTESTED)

Mirrors the macOS D1 menu-bar assistant with Windows parts: `keyboard`
for global hotkeys (Ctrl+Shift+R / Ctrl+Shift+P), clipboard-based
selection capture with restore, and a pywebview panel rendering the same
panel_html as the Mac app.

**Status: no Windows machine has run this yet.** When one is available,
the plan mirrors the macOS bring-up: run `python researchly_win.py` from
a terminal first, fix whatever the traceback says (likely: clipboard
timing constants, hotkey permissions, WebView2 runtime), then build the
.exe with `build_win.bat` (PyInstaller; the --collect-all list will need
the same kind of iteration py2app did on macOS).

Setup on a Windows machine:

    pip install -r ..\requirements.txt
    python -m spacy download en_core_web_sm
    pip install -r requirements-win.txt
    python researchly_win.py

Panel buttons (Replace selection / Copy rewrite) call back through
pywebview's js_api — wire-up lives in `JsApi` and would be the first
thing to verify.
