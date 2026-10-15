"use client";

/**
 * The composer's editor with underlines while writing (S4d R5; DESIGN.md
 * "Underlines while writing").
 *
 * The textarea stays native: typing, IME, paste, undo, spell-check
 * settings and screen readers all work as before. Behind it a mirror with
 * the same font, wrapping, padding and scroll position draws the text in
 * transparent ink, with the underlined stretches carrying their category's
 * line (colour, pattern and thickness from the design tokens). Only the
 * changed paragraphs re-render.
 *
 * The underline escalates: a hover (or the caret resting in it) shows a
 * teaser, the teaser opens the full card, and the revision queue in the
 * results remains the list. Accepting a revision edits the textarea
 * through the browser's own editing command, so Ctrl/Cmd+Z undoes it.
 */
import {
  memo,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type ChangeEvent,
  type KeyboardEvent,
  type PointerEvent,
  type ReactNode,
  type RefObject,
} from "react";
import type { Format } from "@researchly/contract";
import { categoryMeta } from "@/lib/categories";
import { stateLabel } from "@/lib/check-state";
import { asSuggestion, itemAt, itemSummary, paragraphMarks, type LiveItem, type LiveParagraph } from "@/lib/live-paragraphs";
import type { LiveSession, LiveSnapshot } from "@/lib/live-session";
import { CategoryBadge } from "./CategoryIcon";
import { SuggestionCard } from "./SuggestionCard";

/** Where an underline is: its paragraph (by key and occurrence, so an identical paragraph elsewhere is not confused) and the item. */
interface Target {
  key: string;
  occ: number;
  item: LiveItem;
}

interface Teaser extends Target {
  trigger: "hover" | "caret";
  /** Viewport coordinates: where the teaser goes, kept inside the window. */
  left: number;
  top: number;
  /** Too near the bottom of the window: the teaser sits above the words. */
  above: boolean;
}

/** The teaser's place for an underline's line box: under it, inside the window, above it near the bottom. */
function teaserPlace(r: DOMRect): { left: number; top: number; above: boolean } {
  const vw = window.innerWidth;
  const width = Math.min(352, vw - 16);
  const above = r.bottom + 180 > window.innerHeight && r.top > 180;
  return { left: Math.max(8, Math.min(r.left, vw - width - 8)), top: above ? r.top - 6 : r.bottom + 6, above };
}

interface CardAt extends Target {
  /** Coordinates inside the editor's frame. */
  left: number;
  top: number;
}

export function useLiveSnapshot(session: LiveSession): LiveSnapshot {
  return useSyncExternalStore(session.subscribe, session.getSnapshot, session.getSnapshot);
}

/** The nth paragraph (0-based occurrence) with this key, in the current text. */
function findParagraph(snap: LiveSnapshot, key: string, occ: number): LiveParagraph | null {
  let n = 0;
  for (const p of snap.doc.paragraphs) {
    if (p.key !== key) continue;
    if (n === occ) return p;
    n++;
  }
  return null;
}

function occurrenceOf(snap: LiveSnapshot, p: LiveParagraph): number {
  let n = 0;
  for (const q of snap.doc.paragraphs) {
    if (q === p) return n;
    if (q.key === p.key) n++;
  }
  return 0;
}

/* ---------- the mirror ---------- */

const MirrorParagraph = memo(function MirrorParagraph({
  text,
  items,
  pkey,
  occ,
  active,
}: {
  text: string;
  items: readonly LiveItem[];
  pkey: string;
  occ: number;
  active: string | null;
}) {
  if (items.length === 0) return <div data-key={pkey} data-occ={occ}>{text}</div>;
  const runs = paragraphMarks(text, items);
  return (
    <div data-key={pkey} data-occ={occ}>
      {runs.map((r) => {
        if (r.kind === "point") {
          const cat = categoryMeta(r.category).id;
          return <span key={`p${r.at}`} className={`lu-pt lu-${cat}${active && r.ids.includes(active) ? " is-active" : ""}`} data-ids={r.ids.join(" ")} />;
        }
        if (r.ids.length === 0) return <span key={`t${r.start}`}>{r.text}</span>;
        const cat = categoryMeta(r.category ?? "improvement").id;
        return (
          <span
            key={`m${r.start}`}
            className={`lu-mark lu-${cat}${r.ids.length > 1 ? " lu-multi" : ""}${active && r.ids.includes(active) ? " is-active" : ""}`}
            data-ids={r.ids.join(" ")}
            data-testid="underline"
            data-category={cat}
          >
            {r.text}
          </span>
        );
      })}
    </div>
  );
});

/**
 * The lines between paragraphs (blank lines, headings, code), one block per
 * line, so the mirror lays out one paragraph at a time: an edit re-lays out
 * its own block, never the whole text (2026-10-15 performance pass).
 * `where` says how the stretch meets its neighbours: a stretch after a
 * paragraph starts with that paragraph's line break, one before a paragraph
 * ends with the line break that starts it.
 */
const MirrorLines = memo(function MirrorLines({ text, where }: { text: string; where: "lead" | "mid" | "tail" | "all" }) {
  let body = text;
  if (where === "mid" || where === "tail") body = body.slice(1);
  if (where === "mid" || where === "lead") body = body.slice(0, -1);
  if (where === "tail" && text === "") return null;
  if (where === "lead" && text === "") return null;
  return (
    <>
      {body.split("\n").map((line, i) => (
        // An empty line still needs its height: a zero-width space gives it one.
        <div key={i}>{line.trim() === "" ? `${line}\u200b` : line}</div>
      ))}
    </>
  );
});

const Mirror = memo(function Mirror({
  text,
  snap,
  active,
  mirrorRef,
}: {
  text: string;
  snap: LiveSnapshot;
  active: Target | null;
  mirrorRef: RefObject<HTMLDivElement | null>;
}) {
  const nodes: ReactNode[] = [];
  let at = 0;
  const seen = new Map<string, number>();
  const paragraphs = snap.doc.paragraphs;
  if (paragraphs.length === 0) nodes.push(<MirrorLines key="all" text={text} where="all" />);
  for (const p of paragraphs) {
    nodes.push(<MirrorLines key={`g${p.index}`} text={text.slice(at, p.start)} where={p.index === 0 ? "lead" : "mid"} />);
    const occ = seen.get(p.key) ?? 0;
    seen.set(p.key, occ + 1);
    const isActive = active && active.key === p.key && active.occ === occ ? active.item.id : null;
    nodes.push(<MirrorParagraph key={`${p.key}.${occ}`} text={p.text} items={snap.itemsFor(p)} pkey={p.key} occ={occ} active={isActive} />);
    at = p.end;
  }
  if (paragraphs.length) nodes.push(<MirrorLines key="tail" text={text.slice(at)} where="tail" />);
  return (
    <div ref={mirrorRef} className="lu-mirror" aria-hidden="true" data-testid="underline-mirror">
      {nodes}
    </div>
  );
});

/* ---------- the teaser ---------- */

/**
 * The second step after the underline: its category (icon and name), what
 * was noticed and the revision, if there is one. A click on it, or "Why?",
 * opens the full card; "Use it" applies the revision. Referenced by the
 * textarea's aria-describedby while it shows.
 */
export function UnderlineTeaser({
  id,
  item,
  caret,
  place,
  onEnter,
  onLeave,
  onApply,
  onOpen,
}: {
  id: string;
  item: LiveItem;
  /** Shown for the caret (keyboard): it names the shortcut to the card. */
  caret: boolean;
  place: { left: number; top: number; above: boolean };
  onEnter?: () => void;
  onLeave?: () => void;
  onApply: (replacement: string) => void;
  onOpen: () => void;
}) {
  const repl = item.replacements.length ? item.replacements[0]! : null;
  return (
    <div
      id={id}
      className={`lu-teaser${place.above ? " lu-above" : ""}`}
      role="group"
      aria-label="About the underlined words"
      style={{ left: place.left, top: place.top }}
      onPointerEnter={onEnter}
      onPointerLeave={onLeave}
      onClick={(e) => {
        if ((e.target as HTMLElement).closest("button")) return;
        onOpen();
      }}
      data-testid="underline-teaser"
      data-category={item.category}
    >
      <CategoryBadge category={item.category} />
      <p className="lu-teaser-msg">{item.message}</p>
      {repl !== null ? (
        <p className="lu-teaser-repl">
          <span className="card-repl-label">Suggested revision (your call):</span>{" "}
          {repl === "" ? <em>remove this</em> : <q>{repl}</q>}
        </p>
      ) : null}
      <p className="lu-teaser-actions">
        {repl !== null ? (
          <button type="button" className="btn-link" onClick={() => onApply(repl)} data-testid="teaser-apply">
            {repl === "" ? "Remove" : "Use it"}
          </button>
        ) : null}
        <button type="button" className="btn-link" onClick={onOpen} data-testid="teaser-open">
          Why?
        </button>
        {caret ? <span className="lu-kbd">Ctrl + . for the card</span> : null}
      </p>
    </div>
  );
}

/* ---------- the editor ---------- */

export interface LiveEditorProps {
  session: LiveSession;
  value: string;
  format: Format;
  onChange: (value: string) => void;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  id: string;
  describedBy: string;
  invalid: boolean;
  placeholder: string;
  /** Rendered between the editor and the list of underlines (the character counter row). */
  footer?: ReactNode;
}

const TEASER_DELAY_MS = 220;
const TEASER_HIDE_MS = 260;
const CARET_DELAY_MS = 600;
const ANNOUNCE_GAP_MS = 8000;
const LIST_LIMIT = 200;
const NAV_KEYS = new Set(["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End", "PageUp", "PageDown"]);

export function LiveEditor({ session, value, format, onChange, textareaRef, id, describedBy, invalid, placeholder, footer }: LiveEditorProps) {
  const snap = useLiveSnapshot(session);
  const mirrorRef = useRef<HTMLDivElement | null>(null);
  const frameRef = useRef<HTMLDivElement | null>(null);
  const cardRef = useRef<HTMLDivElement | null>(null);
  const [teaser, setTeaser] = useState<Teaser | null>(null);
  const [card, setCard] = useState<CardAt | null>(null);
  const [note, setNote] = useState("");
  const [said, setSaid] = useState("");
  const applying = useRef(false);
  const rects = useRef<{ el: HTMLElement; rects: DOMRect[] }[] | null>(null);
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const caretTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const moveFrame = useRef<number | null>(null);
  const lastAnnounced = useRef({ at: 0, text: "" });
  const announceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const ids = { teaser: useId(), list: useId(), help: useId(), cardTitle: useId() };

  const drawing = snap.enabled && snap.doc.paragraphs.length > 0;
  const drawn = useMemo(() => (snap.enabled ? session.drawn() : []), [session, snap]);
  const hasMarks = drawn.length > 0;

  // The mirror follows every change of the text before the browser paints, so underlines never lag the words.
  useLayoutEffect(() => {
    session.setDocument(value, format);
  }, [session, value, format]);

  useEffect(() => {
    session.setCaretSource(() => textareaRef.current?.selectionStart ?? 0);
  }, [session, textareaRef]);

  const syncScroll = useCallback(() => {
    const ta = textareaRef.current;
    const m = mirrorRef.current;
    if (!ta || !m) return;
    if (m.scrollTop !== ta.scrollTop) m.scrollTop = ta.scrollTop;
    if (m.scrollLeft !== ta.scrollLeft) m.scrollLeft = ta.scrollLeft;
  }, [textareaRef]);

  // After the mirror re-renders, its scroll position follows the textarea's; the cached rectangles are out of date.
  // A new mirror starts where the textarea is scrolled to; after that, scroll events keep them together.
  useLayoutEffect(() => {
    if (hasMarks) syncScroll();
  }, [hasMarks, syncScroll]);
  // Anything drawn may have moved: the cached rectangles are out of date (nothing is measured here).
  useEffect(() => {
    rects.current = null;
  }, [snap.version]);

  // Rectangles are in viewport coordinates: a resize or any scroll makes them stale, and a hover teaser left behind.
  useEffect(() => {
    const onMove = () => {
      rects.current = null;
      setTeaser((t) => (t?.trigger === "hover" ? null : t));
    };
    window.addEventListener("resize", onMove);
    window.addEventListener("scroll", onMove, { passive: true });
    return () => {
      window.removeEventListener("resize", onMove);
      window.removeEventListener("scroll", onMove);
    };
  }, []);

  useEffect(
    () => () => {
      for (const t of [hoverTimer, hideTimer, caretTimer, announceTimer]) if (t.current) clearTimeout(t.current);
      if (moveFrame.current !== null) cancelAnimationFrame(moveFrame.current);
    },
    [],
  );

  /** Polite, and rare: one sentence at most every few seconds, the latest wins. */
  const announce = useCallback((text: string, urgent = false) => {
    if (announceTimer.current) clearTimeout(announceTimer.current);
    const wait = urgent ? 0 : Math.max(0, lastAnnounced.current.at + ANNOUNCE_GAP_MS - Date.now());
    announceTimer.current = setTimeout(() => {
      if (text === lastAnnounced.current.text && !urgent) return;
      lastAnnounced.current = { at: Date.now(), text };
      setSaid(text);
    }, wait);
  }, []);

  // The state, said rarely: a new count once typing has settled, going offline, coming back.
  const stateText = snap.enabled && snap.status.state !== "hidden" && snap.status.state !== "checking" ? stateLabel(snap.status) : "";
  useEffect(() => {
    if (!stateText) return;
    announce(snap.status.state === "offline" ? `Underlines: ${stateText}. Your text is not lost.` : `Underlines: ${stateText}.`, snap.status.state === "offline");
  }, [stateText, snap.status.state, announce]);

  // Underlines gone (switched off, LaTeX, text changed): no teaser or card for them.
  const valid = useCallback(
    (t: Target | null) => {
      if (!t || !snap.enabled) return false;
      const p = findParagraph(snap, t.key, t.occ);
      return Boolean(p && snap.itemsFor(p).some((i) => i.id === t.item.id));
    },
    [snap],
  );
  const shownTeaser = teaser && valid(teaser) ? teaser : null;
  const shownCard = card && valid(card) ? card : null;

  /* ---------- hit-testing ---------- */

  const markRects = () => {
    if (rects.current) return rects.current;
    const m = mirrorRef.current;
    if (!m) return [];
    const box = m.getBoundingClientRect();
    const out: { el: HTMLElement; rects: DOMRect[] }[] = [];
    for (const el of m.querySelectorAll<HTMLElement>("[data-ids]")) {
      const rs = Array.from(el.getClientRects()).filter((r) => r.bottom >= box.top && r.top <= box.bottom);
      if (rs.length) out.push({ el, rects: rs });
    }
    rects.current = out;
    return out;
  };

  /** The underline under a point, as a target and the rectangle of its line. */
  const hit = (x: number, y: number): { target: Target; rect: DOMRect } | null => {
    for (const { el, rects: rs } of markRects()) {
      for (const r of rs) {
        const slack = r.width < 2 ? 5 : 0;
        if (x >= r.left - slack && x <= r.right + slack && y >= r.top && y <= r.bottom) {
          const t = targetOf(el);
          if (t) return { target: t, rect: r };
        }
      }
    }
    return null;
  };

  const targetOf = (el: HTMLElement): Target | null => {
    const host = el.closest<HTMLElement>("[data-key]");
    if (!host) return null;
    const key = host.dataset.key ?? "";
    const occ = Number(host.dataset.occ ?? 0);
    const p = findParagraph(snap, key, occ);
    if (!p) return null;
    const idsHere = (el.dataset.ids ?? "").split(" ");
    const items = snap.itemsFor(p).filter((i) => idsHere.includes(i.id));
    const order = ["correction", "improvement", "convention", "preference"];
    items.sort((a, b) => order.indexOf(a.category) - order.indexOf(b.category) || a.end - a.begin - (b.end - b.begin));
    return items[0] ? { key, occ, item: items[0] } : null;
  };

  /** The first line box of an underline in the mirror, found by its target. */
  const rectOf = (t: Target): DOMRect | null => {
    const m = mirrorRef.current;
    if (!m) return null;
    const host = m.querySelector<HTMLElement>(`[data-key="${CSS.escape(t.key)}"][data-occ="${t.occ}"]`);
    const el = host ? Array.from(host.querySelectorAll<HTMLElement>("[data-ids]")).find((e) => (e.dataset.ids ?? "").split(" ").includes(t.item.id)) : null;
    const r = el?.getClientRects()[0];
    return r ?? null;
  };

  const clearHover = () => {
    if (hoverTimer.current) clearTimeout(hoverTimer.current);
    hoverTimer.current = null;
  };
  const keepTeaser = () => {
    if (hideTimer.current) clearTimeout(hideTimer.current);
    hideTimer.current = null;
  };
  const hideTeaserSoon = () => {
    keepTeaser();
    hideTimer.current = setTimeout(() => setTeaser((t) => (t?.trigger === "hover" ? null : t)), TEASER_HIDE_MS);
  };

  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    if (e.pointerType === "touch" || !hasMarks || card) return;
    const { clientX: x, clientY: y } = e;
    if (moveFrame.current !== null) return;
    moveFrame.current = requestAnimationFrame(() => {
      moveFrame.current = null;
      const h = hit(x, y);
      if (!h) {
        clearHover();
        if (teaser?.trigger === "hover") hideTeaserSoon();
        return;
      }
      keepTeaser();
      if (teaser && teaser.key === h.target.key && teaser.occ === h.target.occ && teaser.item.id === h.target.item.id) return;
      clearHover();
      hoverTimer.current = setTimeout(() => {
        setTeaser({ ...h.target, trigger: "hover", ...teaserPlace(h.rect) });
      }, TEASER_DELAY_MS);
    });
  };

  const onPointerLeave = () => {
    clearHover();
    if (teaser?.trigger === "hover") hideTeaserSoon();
  };

  /* ---------- the caret ---------- */

  const caretTarget = (): Target | null => {
    const ta = textareaRef.current;
    if (!ta || ta.selectionStart !== ta.selectionEnd) return null;
    const at = ta.selectionStart;
    for (const p of snap.doc.paragraphs) {
      if (at < p.start || at > p.end) continue;
      const item = itemAt(snap.itemsFor(p), at - p.start);
      return item ? { key: p.key, occ: occurrenceOf(snap, p), item } : null;
    }
    return null;
  };

  const caretSoon = () => {
    if (caretTimer.current) clearTimeout(caretTimer.current);
    if (!hasMarks) return;
    caretTimer.current = setTimeout(() => {
      const t = caretTarget();
      if (!t) {
        setTeaser((cur) => (cur?.trigger === "caret" ? null : cur));
        return;
      }
      if (teaser && teaser.item.id === t.item.id && teaser.key === t.key) return;
      const r = rectOf(t);
      if (!r) return;
      setTeaser({ ...t, trigger: "caret", ...teaserPlace(r) });
      announce(`${itemSummary(t.item, categoryMeta(t.item.category).label)}. Press Control and full stop for the full card.`, true);
    }, CARET_DELAY_MS);
  };

  /* ---------- the card ---------- */

  const openCard = (t: Target) => {
    const frame = frameRef.current;
    const r = rectOf(t);
    if (!frame || !r) return;
    const box = frame.getBoundingClientRect();
    setTeaser(null);
    clearHover();
    setNote("");
    setCard({ ...t, left: r.left - box.left, top: r.bottom - box.top + 6 });
  };

  // A newly opened card takes focus; Escape or "Back to your text" gives it back.
  const cardKey = card ? `${card.key}.${card.occ}.${card.item.id}` : null;
  useEffect(() => {
    if (cardKey) cardRef.current?.focus();
  }, [cardKey]);

  const closeCard = useCallback(
    (select?: Target) => {
      setCard(null);
      const ta = textareaRef.current;
      if (!ta) return;
      ta.focus();
      if (select) {
        const p = findParagraph(session.getSnapshot(), select.key, select.occ);
        if (p) ta.setSelectionRange(p.start + select.item.begin, p.start + select.item.end);
      }
    },
    [session, textareaRef],
  );

  // A click outside the open card closes it.
  useEffect(() => {
    if (!card) return;
    const onDown = (e: globalThis.PointerEvent) => {
      if (cardRef.current && !cardRef.current.contains(e.target as Node)) setCard(null);
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [card]);

  /* ---------- accepting a revision ---------- */

  const apply = (t: Target, replacement: string) => {
    const ta = textareaRef.current;
    const p = findParagraph(session.getSnapshot(), t.key, t.occ);
    if (!ta || !p) return;
    const a = p.start + t.item.begin;
    const b = p.start + t.item.end;
    if (ta.value.slice(a, b) !== t.item.text) {
      setNote("These words have changed since they were checked, so nothing was replaced.");
      return;
    }
    setCard(null);
    setTeaser(null);
    ta.focus();
    ta.setSelectionRange(a, b);
    applying.current = true;
    let done = false;
    try {
      // The browser's own editing command: it joins the undo history.
      done = document.execCommand(replacement === "" ? "delete" : "insertText", false, replacement);
    } catch {
      done = false;
    }
    if (!done || ta.value.slice(a, a + replacement.length) !== replacement) {
      ta.setRangeText(replacement, a, b, "end");
      ta.dispatchEvent(new Event("input", { bubbles: true }));
    }
    applying.current = false;
    announce(replacement === "" ? "Removed. Undo with Control and Z." : `Replaced with “${replacement}”. Undo with Control and Z.`, true);
  };

  /* ---------- events on the textarea ---------- */

  const onInput = (e: ChangeEvent<HTMLTextAreaElement>) => {
    const v = e.target.value;
    session.setDocument(v, format);
    // A revision just applied is checked again at once; typing waits for the pause.
    session.edit(applying.current ? 250 : undefined);
    if (teaser) setTeaser(null);
    onChange(v);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key === ".") {
      if (!snap.enabled) return;
      e.preventDefault();
      const here = caretTarget();
      if (here) {
        openCard(here);
        return;
      }
      // None at the caret: the next one after it (then the first).
      const at = textareaRef.current?.selectionEnd ?? 0;
      const next = drawn.find((d) => d.paragraph.start + d.item.begin >= at) ?? drawn[0];
      if (next) goTo({ key: next.paragraph.key, occ: occurrenceOf(snap, next.paragraph), item: next.item });
      return;
    }
    if (e.key === "Escape" && teaser) {
      setTeaser(null);
    }
  };

  const onKeyUp = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (NAV_KEYS.has(e.key)) caretSoon();
  };

  /** Select an underline in the text, bring it into view, then open its card. */
  const goTo = (t: Target) => {
    const ta = textareaRef.current;
    const p = findParagraph(snap, t.key, t.occ);
    if (!ta || !p) return;
    ta.focus();
    ta.setSelectionRange(p.start + t.item.begin, p.start + t.item.end);
    // A blur and focus makes every browser scroll the selection into view.
    ta.blur();
    ta.focus();
    requestAnimationFrame(() => {
      syncScroll();
      rects.current = null;
      openCard(t);
    });
  };

  const onCardKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      closeCard(shownCard ?? undefined);
    }
  };

  const describe = [describedBy, shownTeaser ? ids.teaser : null, hasMarks ? ids.help : null].filter(Boolean).join(" ");
  const teaserItem = shownTeaser?.item ?? null;
  const cardItem = shownCard?.item ?? null;
  const cardRepl = cardItem && cardItem.replacements.length ? cardItem.replacements[0]! : null;

  return (
    <>
      <div
        ref={frameRef}
        className={`lu-frame${drawing ? " lu-on" : ""}`}
        onPointerMove={drawing ? onPointerMove : undefined}
        onPointerLeave={drawing ? onPointerLeave : undefined}
      >
        {drawing && hasMarks ? <Mirror text={value} snap={snap} active={shownCard ?? shownTeaser} mirrorRef={mirrorRef} /> : null}
        <textarea
          id={id}
          ref={textareaRef}
          className="editor"
          name="content"
          value={value}
          onChange={onInput}
          onScroll={() => {
            if (hasMarks) {
              syncScroll();
              rects.current = null;
            }
            if (teaser?.trigger === "hover") setTeaser(null);
          }}
          onKeyDown={onKeyDown}
          onKeyUp={onKeyUp}
          onMouseUp={caretSoon}
          onBlur={() => {
            if (caretTimer.current) clearTimeout(caretTimer.current);
          }}
          aria-describedby={describe || undefined}
          aria-invalid={invalid ? true : undefined}
          spellCheck={false}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          rows={12}
          placeholder={placeholder}
          data-testid="editor"
        />
        {shownCard && cardItem ? (
          <div
            ref={cardRef}
            className="lu-card"
            role="dialog"
            aria-labelledby={`msg-u-${cardItem.id}`}
            tabIndex={-1}
            onKeyDown={onCardKeyDown}
            style={{ top: shownCard.top, ["--lu-left" as string]: `${Math.max(0, shownCard.left)}px` }}
            data-testid="underline-card"
          >
            <SuggestionCard
              suggestion={asSuggestion(cardItem, "u-")}
              active={false}
              placeable
              onShowInText={() => closeCard(shownCard)}
              onDismiss={() => {
                session.dismiss(cardItem.id);
                closeCard();
                announce("Underline dismissed for this page.", true);
              }}
            />
            <div className="lu-card-actions">
              {cardRepl !== null ? (
                <button type="button" className="btn btn-secondary" onClick={() => apply(shownCard, cardRepl)} data-testid="underline-apply">
                  {cardRepl === "" ? "Remove these words" : "Use this revision"}
                </button>
              ) : null}
              <button type="button" className="btn btn-quiet" onClick={() => closeCard(shownCard)} data-testid="underline-close">
                Back to your text
              </button>
            </div>
            {note ? (
              <p className="lu-note" role="status">
                {note}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>

      {shownTeaser && teaserItem && !shownCard ? (
        <UnderlineTeaser
          id={ids.teaser}
          item={teaserItem}
          caret={shownTeaser.trigger === "caret"}
          place={shownTeaser}
          onEnter={keepTeaser}
          onLeave={hideTeaserSoon}
          onApply={(r) => apply(shownTeaser, r)}
          onOpen={() => openCard(shownTeaser)}
        />
      ) : null}

      {footer}

      {hasMarks ? (
        <details className="lu-list" data-testid="underline-list">
          <summary>
            Underlines in your text <span className="lu-count">({drawn.length.toLocaleString("en-GB")})</span>
          </summary>
          <p id={ids.help} className="help lu-help">
            Hover over an underline, or put the cursor in it, for a short note. Ctrl + . (⌘ + . on a Mac) opens the full card for
            the underline at the cursor, or the next one; Escape returns to your text.
          </p>
          <ol className="lu-items">
            {drawn.slice(0, LIST_LIMIT).map(({ paragraph, item }) => {
              const occ = occurrenceOf(snap, paragraph);
              const meta = categoryMeta(item.category);
              return (
                <li key={`${paragraph.key}.${occ}.${item.id}`}>
                  <button
                    type="button"
                    className={`btn-link lu-item lu-${meta.id}`}
                    onClick={() => goTo({ key: paragraph.key, occ, item })}
                    data-testid="underline-item"
                  >
                    {itemSummary(item, meta.label)}
                  </button>
                </li>
              );
            })}
          </ol>
          {drawn.length > LIST_LIMIT ? (
            <p className="help">The first {LIST_LIMIT} are listed; press Check for every suggestion in the results.</p>
          ) : null}
        </details>
      ) : null}

      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true" data-testid="underline-announcer">
        {said}
      </div>
    </>
  );
}
