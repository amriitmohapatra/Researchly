#!/usr/bin/env python3
"""Researchly for macOS — Stage D1: menu-bar assistant.

A menu-bar app that brings the Researchly engine to EVERY application:
select text anywhere (Word, browser, Overleaf, Mail…), press

    ⌘⇧R  — Check selection   (typed, explainable suggestions)
    ⌘⇧P  — Polish selection  (rule-composed rewrite with diff)

and a floating panel appears. "Replace selection" pastes the polished text
back into the app you came from. Everything runs locally.

Selection capture: Accessibility API first (kAXSelectedTextAttribute on the
focused element), clipboard simulation (⌘C) as the universal fallback —
your clipboard is restored afterwards.

First run: macOS will ask you to grant Accessibility permission (System
Settings → Privacy & Security → Accessibility). When running from a
terminal, grant it to the TERMINAL app; when running the built
Researchly.app, grant it to Researchly.

Run:  python3 researchly_app.py       (from this folder)
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))           # panel_html
sys.path.insert(0, str(HERE.parent))    # researchly package

import panel_html  # noqa: E402

try:
    import objc  # noqa: F401
    from AppKit import (  # noqa: E402
        NSApplication, NSApp, NSObject, NSStatusBar,
        NSVariableStatusItemLength, NSMenu, NSMenuItem, NSImage,
        NSPanel, NSMakeRect, NSBackingStoreBuffered,
        NSWindowStyleMaskTitled, NSWindowStyleMaskClosable,
        NSWindowStyleMaskResizable, NSWindowStyleMaskNonactivatingPanel,
        NSWindowStyleMaskBorderless,
        NSFloatingWindowLevel, NSScreen, NSEvent,
        NSEventMaskKeyDown, NSEventModifierFlagCommand,
        NSEventModifierFlagShift, NSPasteboard, NSPasteboardTypeString,
        NSButton, NSBezelStyleRounded, NSView,
        NSViewWidthSizable, NSViewHeightSizable, NSViewMaxYMargin,
        NSTimer, NSControlStateValueOn, NSControlStateValueOff,
    )
    from WebKit import WKWebView, WKWebViewConfiguration  # noqa: E402
    from Quartz import (  # noqa: E402
        CGEventCreateKeyboardEvent, CGEventPost, CGEventSetFlags,
        kCGHIDEventTap, kCGEventFlagMaskCommand,
    )
    from ApplicationServices import (  # noqa: E402
        AXUIElementCreateSystemWide, AXUIElementCopyAttributeValue,
        AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt,
    )
    from PyObjCTools import AppHelper  # noqa: E402
except ImportError as e:  # pragma: no cover — non-mac / missing pyobjc
    print("Researchly desktop needs macOS with pyobjc installed:\n"
          "    pip3 install -r requirements-desktop.txt\n"
          f"(import failed: {e})")
    sys.exit(1)

KEY_C, KEY_V = 8, 9                      # kVK_ANSI_C / kVK_ANSI_V
PANEL_W, PANEL_H, BAR_H = 440, 580, 44

# ---- D2 live watcher ------------------------------------------------------
import json as _json  # noqa: E402

PREFS_FILE = Path.home() / ".researchly" / "desktop.json"
WATCH_INTERVAL = 2.5                     # seconds between focus polls
WATCH_MIN_CHARS = 80                     # ignore tiny fields
WATCH_MAX_CHARS = 20_000                 # cap huge documents (check tail)
BADGE_W, BADGE_H = 56, 24


def load_prefs() -> dict:
    try:
        if PREFS_FILE.exists():
            return _json.loads(PREFS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"watch": False, "deny": []}


def save_prefs(prefs: dict):
    try:
        PREFS_FILE.parent.mkdir(exist_ok=True)
        PREFS_FILE.write_text(_json.dumps(prefs, indent=1),
                              encoding="utf-8")
    except Exception:
        pass


def _decode_ax_frame(element):
    """(x, y, w, h) of an AX element in top-left screen coords, or None.
    AXValueGetValue decoding varies across pyobjc versions — every step is
    defensive; callers fall back to a screen-corner badge."""
    try:
        from ApplicationServices import AXValueGetValue
        import Quartz
        k_point = getattr(__import__("ApplicationServices"),
                          "kAXValueCGPointType", 1)
        k_size = getattr(__import__("ApplicationServices"),
                         "kAXValueCGSizeType", 2)
        err, pos_v = AXUIElementCopyAttributeValue(element, "AXPosition",
                                                   None)
        err2, size_v = AXUIElementCopyAttributeValue(element, "AXSize",
                                                     None)
        if err != 0 or err2 != 0:
            return None
        ok1, pt = AXValueGetValue(pos_v, k_point, None)
        ok2, sz = AXValueGetValue(size_v, k_size, None)
        if not (ok1 and ok2):
            return None
        return (float(pt.x), float(pt.y), float(sz.width),
                float(sz.height))
    except Exception:
        return None


def get_focused_text_and_frame():
    """Full text of the focused editable element via AX, plus its frame.
    Returns (text|None, frame|None). Browsers/Electron mostly return None —
    the badge simply stays hidden there (documented D2 limit)."""
    try:
        system = AXUIElementCreateSystemWide()
        err, focused = AXUIElementCopyAttributeValue(
            system, "AXFocusedUIElement", None)
        if err != 0 or focused is None:
            return None, None
        err, value = AXUIElementCopyAttributeValue(focused, "AXValue", None)
        if err != 0 or not isinstance(value, str) or not value.strip():
            return None, None
        return str(value), _decode_ax_frame(focused)
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# Engine wrapper (background-thread friendly)
# ---------------------------------------------------------------------------

class Engine:
    def __init__(self):
        self.nlp = None
        self.error = None
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            from researchly import api
            self.nlp = api.get_nlp()
            # import registers all rules
            from researchly import (rules_lexical, rules_syntax,  # noqa: F401
                                    rules_spelling, rules_grammar)
            print("engine ready")
        except Exception as e:  # surfaced in the panel on first use
            self.error = f"{type(e).__name__}: {e}"

    def check(self, text: str):
        """One pass. This used to run the whole engine twice and parse three
        times — once for the suggestions, again purely to count hidden
        preferences, and once more for metrics."""
        from researchly import api
        a = api.analyze(text, kind="plain", nlp=self.nlp)
        return ([s.to_dict() for s in a.suggestions], a.metrics,
                a.hidden_preferences, a.health)

    def status(self):
        from researchly import api
        return api.status()

    def polish(self, text: str):
        from researchly.transform import polish
        from researchly import config as config_mod
        return polish(text, self.nlp, kind="plain",
                      disabled=config_mod.load().disabled)


# ---------------------------------------------------------------------------
# Selection capture / paste-back
# ---------------------------------------------------------------------------

def _post_key(keycode: int, cmd: bool):
    for down in (True, False):
        ev = CGEventCreateKeyboardEvent(None, keycode, down)
        if cmd:
            CGEventSetFlags(ev, kCGEventFlagMaskCommand)
        CGEventPost(kCGHIDEventTap, ev)


def get_selection_ax() -> str | None:
    """Selected text via the Accessibility API (no clipboard involved)."""
    try:
        system = AXUIElementCreateSystemWide()
        err, focused = AXUIElementCopyAttributeValue(
            system, "AXFocusedUIElement", None)
        if err != 0 or focused is None:
            return None
        err, sel = AXUIElementCopyAttributeValue(
            focused, "AXSelectedText", None)
        if err == 0 and sel:
            return str(sel)
    except Exception:
        pass
    return None


def get_selection_clipboard() -> str | None:
    """Universal fallback: simulate ⌘C, read pasteboard, restore it."""
    pb = NSPasteboard.generalPasteboard()
    old = pb.stringForType_(NSPasteboardTypeString)
    old_count = pb.changeCount()
    _post_key(KEY_C, cmd=True)
    # wait for the target app to service the copy
    for _ in range(30):                      # up to ~1.5 s
        time.sleep(0.05)
        if pb.changeCount() != old_count:
            break
    text = pb.stringForType_(NSPasteboardTypeString)
    got = text if pb.changeCount() != old_count else None
    # restore the user's clipboard
    if old is not None:
        pb.clearContents()
        pb.setString_forType_(old, NSPasteboardTypeString)
    return got


def capture_selection() -> str:
    return get_selection_ax() or get_selection_clipboard() or ""


def paste_replacement(text: str):
    """Put `text` on the clipboard and ⌘V into the frontmost app.
    The panel is non-activating, so focus never left the target app."""
    pb = NSPasteboard.generalPasteboard()
    old = pb.stringForType_(NSPasteboardTypeString)
    pb.clearContents()
    pb.setString_forType_(text, NSPasteboardTypeString)
    time.sleep(0.05)
    _post_key(KEY_V, cmd=True)

    def restore():
        time.sleep(0.6)                       # let the paste land first
        if old is not None:
            pb.clearContents()
            pb.setString_forType_(old, NSPasteboardTypeString)
    threading.Thread(target=restore, daemon=True).start()


def frontmost_app_name() -> str:
    try:
        from AppKit import NSWorkspace
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return str(app.localizedName()) if app else ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# The app
# ---------------------------------------------------------------------------

class ResearchlyApp(NSObject):

    def applicationDidFinishLaunching_(self, _note):
        self.engine = Engine()
        self.pending_polish = None            # last PolishResult
        self.busy = False

        # menu-bar item
        self.status = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength)
        icon = HERE / "assets" / "menubar.png"
        btn = self.status.button()
        if icon.exists():
            img = NSImage.alloc().initWithContentsOfFile_(str(icon))
            img.setSize_((18, 18))
            img.setTemplate_(True)            # adapts to dark/light menu bar
            btn.setImage_(img)
        else:
            btn.setTitle_("R")

        # D2 watcher state
        self.prefs = load_prefs()
        self.watch_busy = False
        self.watch_last_hash = None
        self.watch_html = None
        self.badge = None
        self.badge_button = None

        menu = NSMenu.alloc().init()
        for title, action, key in (
                ("Check selection (⌘⇧R)", "menuCheck:", ""),
                ("Polish selection (⌘⇧P)", "menuPolish:", ""),
                (None, None, None),
                ("Open panel", "menuOpenPanel:", ""),
                (None, None, None),
                ("Live watching (beta)", "menuToggleWatch:", ""),
                ("Pause watching in current app", "menuPauseApp:", ""),
                (None, None, None),
                ("Quit Researchly", "terminate:", "q")):
            if title is None:
                menu.addItem_(NSMenuItem.separatorItem())
            else:
                item = NSMenuItem.alloc(
                ).initWithTitle_action_keyEquivalent_(title, action, key)
                if action == "menuToggleWatch:":
                    item.setState_(
                        NSControlStateValueOn if self.prefs.get("watch")
                        else NSControlStateValueOff)
                    self._watch_menu_item = item
                menu.addItem_(item)
        self.status.setMenu_(menu)

        # D2 poll timer (cheap when watching is off)
        self._watch_timer = \
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                WATCH_INTERVAL, self, "watchTick:", None, True)

        self._build_panel()

        # accessibility permission (prompts on first run)
        trusted = AXIsProcessTrustedWithOptions(
            {kAXTrustedCheckOptionPrompt: True})
        if not trusted:
            self._show_html(panel_html.render_message(
                "One-time setup",
                "Grant Accessibility permission in System Settings → "
                "Privacy & Security → Accessibility (to the Terminal if "
                "running from a terminal; to Researchly if running the "
                "app), then press the hotkey again."))

        # global + local hotkey monitors
        def handler(event):
            self._handle_key(event)
        def local_handler(event):
            self._handle_key(event)
            return event
        self._global_monitor = \
            NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                NSEventMaskKeyDown, handler)
        self._local_monitor = \
            NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
                NSEventMaskKeyDown, local_handler)

        print("Researchly is in your menu bar. ⌘⇧R = check, ⌘⇧P = polish.")

    # -- hotkeys ------------------------------------------------------------

    @objc.python_method
    def _handle_key(self, event):
        try:
            flags = event.modifierFlags()
            want = NSEventModifierFlagCommand | NSEventModifierFlagShift
            if (flags & want) != want:
                return
            ch = (event.charactersIgnoringModifiers() or "").lower()
        except Exception:
            return
        if ch == "r":
            self._run("check")
        elif ch == "p":
            self._run("polish")

    def menuCheck_(self, _s):
        self._run("check")

    def menuPolish_(self, _s):
        self._run("polish")

    def menuOpenPanel_(self, _s):
        self.panel.orderFrontRegardless()

    # -- core flow ----------------------------------------------------------

    @objc.python_method
    def _run(self, mode: str):
        if self.busy:
            return
        self.busy = True
        threading.Thread(target=self._worker, args=(mode,),
                         daemon=True).start()

    @objc.python_method
    def _worker(self, mode: str):
        try:
            app_name = frontmost_app_name()
            text = capture_selection()
            if not text.strip():
                AppHelper.callAfter(self._show_html, panel_html.render_message(
                    "No selection",
                    "Select some text in any app, then press "
                    "⌘⇧R (check) or ⌘⇧P (polish)."))
                return
            if self.engine.error:
                AppHelper.callAfter(self._show_html, panel_html.render_message(
                    "Engine failed to load", self.engine.error))
                return
            if self.engine.nlp is None:
                AppHelper.callAfter(self._show_html, panel_html.render_message(
                    "Warming up", "The language model is still loading "
                    "(first run takes ~15s). Try again in a moment."))
                return

            from researchly import telemetry
            if mode == "check":
                suggestions, mets, hidden, health = self.engine.check(text)
                by = {}
                for s in suggestions:
                    k = (s["rule_id"], s["section"])
                    by[k] = by.get(k, 0) + 1
                for (rule, section), n in by.items():
                    telemetry.log_event("shown", rule, section=section,
                                        source="desktop", count=n)
                html = panel_html.render_check(
                    suggestions, mets, hidden, source_app=app_name,
                    health=health)
                AppHelper.callAfter(self._show_check, html)
            else:
                result = self.engine.polish(text)
                self.pending_polish = result
                html = panel_html.render_polish(result, source_app=app_name)
                AppHelper.callAfter(self._show_polish, html,
                                    result.changed)
        except Exception as e:
            AppHelper.callAfter(self._show_html, panel_html.render_message(
                "Error", f"{type(e).__name__}: {e}"))
        finally:
            self.busy = False

    # -- panel --------------------------------------------------------------

    @objc.python_method
    def _build_panel(self):
        screen = NSScreen.mainScreen().visibleFrame()
        x = screen.origin.x + screen.size.width - PANEL_W - 24
        y = screen.origin.y + screen.size.height - PANEL_H - 24
        style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
                 | NSWindowStyleMaskResizable
                 | NSWindowStyleMaskNonactivatingPanel)
        self.panel = NSPanel.alloc(
        ).initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y, PANEL_W, PANEL_H), style,
            NSBackingStoreBuffered, False)
        self.panel.setTitle_("Researchly")
        self.panel.setLevel_(NSFloatingWindowLevel)
        self.panel.setHidesOnDeactivate_(False)
        self.panel.setReleasedWhenClosed_(False)

        content = self.panel.contentView()
        b = content.bounds()

        self.webview = WKWebView.alloc().initWithFrame_configuration_(
            NSMakeRect(0, BAR_H, b.size.width, b.size.height - BAR_H),
            WKWebViewConfiguration.alloc().init())
        self.webview.setAutoresizingMask_(
            NSViewWidthSizable | NSViewHeightSizable)
        content.addSubview_(self.webview)

        bar = NSView.alloc().initWithFrame_(
            NSMakeRect(0, 0, b.size.width, BAR_H))
        bar.setAutoresizingMask_(NSViewWidthSizable | NSViewMaxYMargin)
        content.addSubview_(bar)
        self._bar = bar

        self.btn_replace = self._button(bar, "Replace selection",
                                        "doReplace:", 10, 150)
        self.btn_copy = self._button(bar, "Copy rewrite", "doCopy:", 168, 110)
        self._set_polish_buttons(False)

    @objc.python_method
    def _button(self, parent, title, action, x, w):
        btn = NSButton.alloc().initWithFrame_(NSMakeRect(x, 8, w, 28))
        btn.setTitle_(title)
        btn.setBezelStyle_(NSBezelStyleRounded)
        btn.setTarget_(self)
        btn.setAction_(action)
        parent.addSubview_(btn)
        return btn

    @objc.python_method
    def _set_polish_buttons(self, on: bool):
        self.btn_replace.setHidden_(not on)
        self.btn_copy.setHidden_(not on)

    @objc.python_method
    def _show_html(self, html: str):
        self.webview.loadHTMLString_baseURL_(html, None)
        self._set_polish_buttons(False)
        self.panel.orderFrontRegardless()

    @objc.python_method
    def _show_check(self, html: str):
        self._show_html(html)

    @objc.python_method
    def _show_polish(self, html: str, changed: bool):
        self.webview.loadHTMLString_baseURL_(html, None)
        self._set_polish_buttons(bool(changed))
        self.panel.orderFrontRegardless()

    # -- D2 live watcher -----------------------------------------------------

    def watchTick_(self, _timer):
        if not self.prefs.get("watch") or self.watch_busy:
            return
        if self.engine.nlp is None or self.engine.error:
            return
        app_name = frontmost_app_name()
        if app_name in set(self.prefs.get("deny") or []):
            self._hide_badge()
            return
        text, frame = get_focused_text_and_frame()
        if not text or len(text.strip()) < WATCH_MIN_CHARS:
            self._hide_badge()
            return
        if len(text) > WATCH_MAX_CHARS:
            text = text[-WATCH_MAX_CHARS:]      # check the recent tail
        h = hash(text)
        if h == self.watch_last_hash:
            return
        self.watch_last_hash = h
        self.watch_busy = True
        threading.Thread(target=self._watch_worker,
                         args=(text, app_name, frame),
                         daemon=True).start()

    @objc.python_method
    def _watch_worker(self, text, app_name, frame):
        try:
            suggestions, mets, hidden, health = self.engine.check(text)
            self.watch_html = panel_html.render_check(
                suggestions, mets, hidden, source_app=app_name,
                health=health)
            AppHelper.callAfter(self._update_badge, len(suggestions), frame)
        except Exception:
            pass
        finally:
            self.watch_busy = False

    @objc.python_method
    def _ensure_badge(self):
        if self.badge is not None:
            return
        style = NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel
        self.badge = NSPanel.alloc(
        ).initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, BADGE_W, BADGE_H), style,
            NSBackingStoreBuffered, False)
        self.badge.setLevel_(NSFloatingWindowLevel)
        self.badge.setHidesOnDeactivate_(False)
        self.badge.setReleasedWhenClosed_(False)
        btn = NSButton.alloc().initWithFrame_(
            NSMakeRect(0, 0, BADGE_W, BADGE_H))
        btn.setBezelStyle_(NSBezelStyleRounded)
        btn.setTarget_(self)
        btn.setAction_("badgeClicked:")
        self.badge.contentView().addSubview_(btn)
        self.badge_button = btn

    @objc.python_method
    def _update_badge(self, count, frame):
        if count <= 0:
            self._hide_badge()
            return
        self._ensure_badge()
        self.badge_button.setTitle_(f"R {count}")
        screen = NSScreen.mainScreen().frame()
        if frame:
            fx, fy, fw, fh = frame               # AX: top-left origin
            x = fx + fw - BADGE_W - 8
            y = screen.size.height - fy - BADGE_H - 4   # flip to NS coords
        else:                                    # fallback: top-right corner
            vis = NSScreen.mainScreen().visibleFrame()
            x = vis.origin.x + vis.size.width - BADGE_W - 16
            y = vis.origin.y + vis.size.height - BADGE_H - 8
        self.badge.setFrame_display_(
            NSMakeRect(x, y, BADGE_W, BADGE_H), True)
        self.badge.orderFrontRegardless()

    @objc.python_method
    def _hide_badge(self):
        if self.badge is not None:
            self.badge.orderOut_(None)

    def badgeClicked_(self, _sender):
        if self.watch_html:
            self._show_html(self.watch_html)

    def menuToggleWatch_(self, item):
        on = not bool(self.prefs.get("watch"))
        self.prefs["watch"] = on
        save_prefs(self.prefs)
        item.setState_(NSControlStateValueOn if on
                       else NSControlStateValueOff)
        if not on:
            self._hide_badge()

    def menuPauseApp_(self, _item):
        app_name = frontmost_app_name()
        if not app_name:
            return
        deny = set(self.prefs.get("deny") or [])
        deny.add(app_name)
        self.prefs["deny"] = sorted(deny)
        save_prefs(self.prefs)
        self._hide_badge()
        self._show_html(panel_html.render_message(
            "Watching paused",
            f"Live watching disabled for {app_name}. Edit "
            f"~/.researchly/desktop.json to undo."))

    # -- polish actions ------------------------------------------------------

    def doReplace_(self, _s):
        if not self.pending_polish or not self.pending_polish.changed:
            return
        from researchly import telemetry
        telemetry.log_event("applied", "POLISH", source="desktop")
        text = self.pending_polish.rewritten
        threading.Thread(target=paste_replacement, args=(text,),
                         daemon=True).start()
        self.panel.orderOut_(None)

    def doCopy_(self, _s):
        if not self.pending_polish:
            return
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        pb.setString_forType_(self.pending_polish.rewritten,
                              NSPasteboardTypeString)


def main():
    app = NSApplication.sharedApplication()
    delegate = ResearchlyApp.alloc().init()
    app.setDelegate_(delegate)
    # No dock icon when run as a script:
    from AppKit import NSApplicationActivationPolicyAccessory
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
