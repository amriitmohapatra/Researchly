"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { AnalyzeResponse, SourceInfo } from "@researchly/contract";
import { CATEGORIES, CATEGORY_ORDER, countByCategory, sectionLabel } from "@/lib/categories";
import { resolveSpans, segment } from "@/lib/segments";
import { buildLocator, isMultiFile } from "@/lib/source";
import { applyFilter, hiddenPreferenceCount, shownSuggestions, type Filter } from "@/lib/view";
import { CategoryIcon } from "./CategoryIcon";
import { DocumentView } from "./DocumentView";
import { HealthBanner } from "./HealthBanner";
import { MetricsPanel } from "./MetricsPanel";
import { SuggestionCard, type CardActions } from "./SuggestionCard";

interface Props {
  data: AnalyzeResponse;
  /** Exactly the text that was sent; offsets refer to this, not to the live editor. */
  submittedText: string;
  showPreferences: boolean;
  stale: boolean;
  busy: boolean;
  onRevealPreferences: () => void;
  /** Present when the text came from an uploaded file (read-only view). */
  source?: SourceInfo | null;
  /** Signed-in card actions (mute, add to dictionary). */
  actions?: CardActions | null;
}

type FocusRequest = { id: string; target: "mark" | "card"; seq: number };

const secondsFmt = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1 });

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

const lineFmt = new Intl.NumberFormat("en-GB");

export function Results({ data, submittedText, showPreferences, stale, busy, onRevealPreferences, source, actions }: Props) {
  const [filter, setFilter] = useState<Filter>("all");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [focusReq, setFocusReq] = useState<FocusRequest | null>(null);
  const docColRef = useRef<HTMLDivElement>(null);

  const shown = useMemo(() => shownSuggestions(data, showPreferences), [data, showPreferences]);
  const counts = useMemo(() => countByCategory(shown), [shown]);
  const effectiveFilter: Filter = filter !== "all" && !showPreferences && filter === "preference" ? "all" : filter;
  const visible = useMemo(() => applyFilter(shown, effectiveFilter), [shown, effectiveFilter]);
  const resolved = useMemo(() => resolveSpans(submittedText, visible), [submittedText, visible]);
  const segments = useMemo(() => segment(submittedText, resolved), [submittedText, resolved]);
  const placeable = useMemo(() => new Set(resolved.map((r) => r.id)), [resolved]);
  const hidden = hiddenPreferenceCount(data, showPreferences);
  // A multi-file upload (an Overleaf project): each card says which file and line it is in.
  const locate = useMemo(
    () => (source && isMultiFile(source.segments) ? buildLocator(source.text, source.segments) : null),
    [source],
  );

  useEffect(() => {
    if (!focusReq) return;
    const el =
      focusReq.target === "mark"
        ? docColRef.current?.querySelector<HTMLElement>(`[data-sids~="${CSS.escape(focusReq.id)}"]`)
        : document.getElementById(`card-${focusReq.id}`);
    if (!el) return;
    el.scrollIntoView({ block: "center", inline: "nearest", behavior: prefersReducedMotion() ? "auto" : "smooth" });
    el.focus({ preventScroll: true });
  }, [focusReq]);

  const onSelectFromText = useCallback(
    (ids: readonly string[]) => {
      if (ids.length === 0) return;
      // Overlapping highlights: repeated clicks cycle through every suggestion on that stretch.
      const i = activeId ? ids.indexOf(activeId) : -1;
      const next = i >= 0 && ids.length > 1 ? ids[(i + 1) % ids.length]! : ids[0]!;
      setActiveId(next);
      setFocusReq((r) => ({ id: next, target: "card", seq: (r?.seq ?? 0) + 1 }));
    },
    [activeId],
  );

  const onShowInText = useCallback((id: string) => {
    setActiveId(id);
    setFocusReq((r) => ({ id, target: "mark", seq: (r?.seq ?? 0) + 1 }));
  }, []);

  const sections = data.sections_detected.map(sectionLabel).filter((s): s is string => s !== null);
  const seconds = secondsFmt.format(data.elapsed_ms < 10_000 ? data.elapsed_ms / 1000 : Math.round(data.elapsed_ms / 1000));
  const chips: Filter[] = ["all", ...CATEGORY_ORDER.filter((c) => c !== "preference" || showPreferences)];

  // When no suggestion is shown the note still has to be reachable, so it renders in either layout.
  const hiddenNote =
    hidden > 0 ? (
      <p className="hidden-prefs" data-testid="hidden-prefs">
        <CategoryIcon category="preference" />
        <span>
          {hidden} {hidden === 1 ? "preference" : "preferences"} hidden.
        </span>{" "}
        <button type="button" className="btn-link" onClick={onRevealPreferences} aria-label={`Show ${hidden} hidden preferences`}>
          Show
        </button>
      </p>
    ) : null;

  return (
    <section className="results" aria-labelledby="results-heading" aria-busy={busy} data-testid="results">
      <div className="results-head">
        <h2 id="results-heading" className="results-title">
          {shown.length === 0 ? "No suggestions" : `${shown.length} ${shown.length === 1 ? "suggestion" : "suggestions"}`}
        </h2>
        <p className="muted results-meta">
          {sections.length > 0 ? <>Sections detected: {sections.join(", ")}</> : <>No section headings detected</>}
          {" · "}checked in {seconds}&nbsp;s
        </p>
      </div>

      {stale ? (
        <p className="notice notice-quiet" data-testid="stale-note">
          You have edited the text since this check. The highlights below refer to the version you checked.
        </p>
      ) : null}

      <HealthBanner health={data.health} />

      {shown.length === 0 ? (
        <>
          {hiddenNote}
          <div className="empty" data-testid="empty-state">
            <p className="empty-title">No suggestions. That&rsquo;s not a score.</p>
            <p className="muted">It means none of our checks fired on this text. The read-outs below still describe it.</p>
          </div>
        </>
      ) : (
        <>
          <div className="toolbar">
            <div className="filters" role="group" aria-label="Filter suggestions by category">
              {chips.map((c) => {
                const n = c === "all" ? shown.length : counts[c];
                const label = c === "all" ? "All" : CATEGORIES[c].plural;
                return (
                  <button
                    key={c}
                    type="button"
                    className={`chip-btn chip-${c}`}
                    aria-pressed={effectiveFilter === c}
                    onClick={() => setFilter(c)}
                    data-testid={`filter-${c}`}
                  >
                    {c !== "all" ? <CategoryIcon category={c} /> : null}
                    <span className="chip-label">{label}</span>
                    <span className="chip-count">{n}</span>
                  </button>
                );
              })}
            </div>
            {hiddenNote}
          </div>
          <p className="filter-blurb muted">
            {effectiveFilter === "all"
              ? "Conventions are research-writing norms you may choose to follow. They are not errors."
              : CATEGORIES[effectiveFilter].blurb}
          </p>

          <div className="results-grid">
            <div className="doc-col" ref={docColRef}>
              <h3 className="col-title">{source ? "Your file, as Researchly read it" : "Your text"}</h3>
              <p id="doc-help" className="help">
                {source ? "Read-only. " : ""}Select a highlight to open its suggestion. Keyboard: Tab into the text, move
                with the arrow keys, press Enter.
              </p>
              <DocumentView
                segments={segments}
                activeId={activeId}
                onSelect={onSelectFromText}
                label={source ? "Text read from your file, with highlighted suggestions" : undefined}
              />
            </div>
            <div className="list-col">
              <h3 className="col-title">Suggestions</h3>
              {visible.length === 0 ? (
                <p className="muted">No {CATEGORIES[effectiveFilter as keyof typeof CATEGORIES]?.plural.toLowerCase()} in this check.</p>
              ) : (
                <ol className="cards" aria-label="Suggestions, in document order">
                  {visible.map((s) => {
                    const at = locate?.(s.span.start);
                    return (
                      <li key={s.id}>
                        <SuggestionCard
                          suggestion={s}
                          active={s.id === activeId}
                          placeable={placeable.has(s.id)}
                          onShowInText={onShowInText}
                          location={at ? `${at.path}, line ${lineFmt.format(at.line)}` : null}
                          actions={actions}
                        />
                      </li>
                    );
                  })}
                </ol>
              )}
            </div>
          </div>
        </>
      )}

      {data.metrics ? <MetricsPanel metrics={data.metrics} /> : null}

      <p className="engine-meta muted">
        Checked by engine {data.engine.service_version} (core {data.engine.core_version}) with{" "}
        {data.engine.rules_loaded} rules. Each suggestion names its source; open &ldquo;Why?&rdquo; for the reasoning.
      </p>
    </section>
  );
}
