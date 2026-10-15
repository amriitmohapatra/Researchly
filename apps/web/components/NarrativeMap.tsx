"use client";

import { useId, type ReactNode } from "react";
import type { EvidenceSpan, HedgingPoint, MissingLink, NarrativeMove, NarrativeSection, ReviewerUnit } from "@researchly/contract";
import { showKey } from "@/lib/evidence";
import type { NarrativeState } from "@/lib/profiles";
import { Quote, shortQuote, type ShowInText } from "./EvidenceLinks";
import { LessonDisclosure } from "./LessonDisclosure";

/** Where a move's or a link's sentence can be shown in the text (Codex review #3). */
interface Showing {
  onShow: ShowInText | null;
  canShow?: (span: EvidenceSpan) => boolean;
}

interface Props {
  /** "Show in text" for each placed sentence; absent on paper. */
  onShowInText?: ShowInText | null;
  canShow?: (span: EvidenceSpan) => boolean;
  /** What the check assumed about how much of the document this is, with its override (Codex review #4). */
  scopeLine?: ReactNode;
  state: NarrativeState;
  /** When the surface has a Draft/Revise control: switches to Revise and checks again. */
  onSwitchToRevise?: () => void;
  /**
   * "screen" (default): the strip is a row of cells and a present move's
   * sentence sits behind a disclosure. "print": the strip is text rows and
   * every sentence is open, since paper cannot be clicked.
   */
  variant?: "screen" | "print";
}

/** The status word a reader sees: never colour alone (DESIGN.md). */
export const STATUS_WORD: Record<NarrativeMove["status"], string> = {
  present: "present",
  // The map reads wording: it can say a move was not detected, never that it is missing (Codex review N5).
  not_detected: "not detected",
  out_of_order: "out of order",
};

const per100 = new Intl.NumberFormat("en-GB", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/**
 * The narrative map (S4b, ADR-05): the third view of one check. Read top
 * to bottom: the engine's one-line note; one strip per section with its
 * expected moves in order, each marked present, not detected or out of order
 * by shape and word; under the strip, each not-detected or out-of-order move
 * opens to its question, the lesson in everyday words and a frame to fill
 * in, and each present move keeps the writer's own sentence behind "Show
 * the sentence". A missing move and a missing link that name a Learn card
 * open it under "The lesson" (S4; screen only), and a link's sentences sit
 * behind "Show the sentence". Then the argument's missing links, the hedging trajectory
 * as a table of labelled values, and the source set like a card's. Never a
 * score: no counts beyond "2 of 5 moves", no meters, no colour by verdict.
 */
export function NarrativeMap({ state, onSwitchToRevise, variant = "screen", onShowInText = null, canShow, scopeLine = null }: Props) {
  // Heading ids from useId: the printable report mounts a second map beside the screen's.
  const idBase = useId();
  const linksTitle = `${idBase}-links`;
  const hedgingTitle = `${idBase}-hedging`;
  if (state.kind === "needs_revise") {
    return (
      <p className="brief-line" data-testid="narrative-needs-revise">
        <span>The narrative map reads the whole document, so it needs Revise mode.</span>
        {onSwitchToRevise ? (
          <button type="button" className="btn-link" onClick={onSwitchToRevise} data-testid="narrative-switch-revise">
            Switch to Revise
          </button>
        ) : null}
      </p>
    );
  }
  if (state.kind === "missing") {
    return (
      <p className="brief-line" data-testid="narrative-missing">
        This engine did not return a narrative map for this check.
      </p>
    );
  }
  const n = state.narrative;
  const links = n.missing_links ?? [];
  const hedging = n.hedging ?? [];
  const unmapped = (n.unmapped ?? []).filter((u) => u.trim());
  const print = variant === "print";
  const showing: Showing = { onShow: print ? null : onShowInText, canShow };
  const units = n.units ?? [];
  const unitsTitle = `${idBase}-units`;
  return (
    <div className={`nmap${print ? " nmap-print" : ""}`} data-testid="narrative-map">
      <p className="help nmap-note" data-testid="narrative-note">
        {n.note}
      </p>
      {scopeLine}
      {units.length > 0 ? (
        <section className="nmap-units" aria-labelledby={unitsTitle} data-testid="narrative-units">
          <h4 id={unitsTitle} className="col-title">
            Comments and replies
          </h4>
          <ol className="nmap-units-list">
            {units.map((u, i) => (
              <li key={`${u.label}-${i}`} className="nmap-unit" data-testid="narrative-unit">
                <Unit unit={u} index={i} showing={showing} />
              </li>
            ))}
          </ol>
          {print ? null : <LessonDisclosure learnRef={units[0]!.learn_ref} />}
        </section>
      ) : null}
      {n.sections.length > 0 ? (
        <ol className="nmap-sections">
          {n.sections.map((s, i) => (
            <li key={`${s.section}-${i}`} className="nmap-section" data-testid="narrative-section" data-section={s.section}>
              <Strip section={s} print={print} showing={showing} />
            </li>
          ))}
        </ol>
      ) : null}
      {unmapped.length > 0 ? (
        <p className="nmap-unmapped muted" data-testid="narrative-unmapped">
          Headings with no expected moves: {unmapped.join(", ")}
        </p>
      ) : null}

      <section className="nmap-links" aria-labelledby={linksTitle} data-testid="narrative-links">
        <h4 id={linksTitle} className="col-title">
          Argument: missing links
        </h4>
        {links.length === 0 ? (
          <p className="muted nmap-links-none">No missing links in the argued sections of this check.</p>
        ) : (
          <ul className="nmap-links-list">
            {links.map((l, i) => (
              <li key={`${l.section}-${l.code}-${i}`} className="nmap-link" data-testid="narrative-link" data-code={l.code}>
                <p className="nmap-link-head">
                  <span className="nmap-link-section">{l.label}</span>
                </p>
                <p className="nmap-link-msg">{l.message}</p>
                <LinkEvidence link={l} print={print} showing={showing} where={`link-${i}`} />
                {print ? null : <LessonDisclosure learnRef={l.learn_ref} />}
                <p className="card-source">
                  <span className="card-source-label">Source:</span> <cite>{l.source}</cite>
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {hedging.length > 0 ? (
        <section className="nmap-hedging" aria-labelledby={hedgingTitle} data-testid="narrative-hedging">
          <h4 id={hedgingTitle} className="col-title">
            Hedging across the document
          </h4>
          <p className="help nmap-hedging-help">
            Hedges (may, suggest, appear) and boosters (clearly, prove) per 100 words in each section, with a reading of
            each. A trajectory to notice, not a score.
          </p>
          <HedgingTable rows={hedging} />
        </section>
      ) : null}

      <p className="card-source nmap-source">
        <span className="card-source-label">Source:</span> <cite>{n.source}</cite>
      </p>
    </div>
  );
}

function movesPhrase(s: NarrativeSection): string {
  return `${s.present} of ${s.expected} ${s.expected === 1 ? "move" : "moves"} present`;
}

/** One reviewer comment beside the reply under it: described, never judged (Codex review N5). */
function Unit({ unit: u, index, showing }: { unit: ReviewerUnit; index: number; showing: Showing }) {
  return (
    <>
      <p className="nmap-unit-label">{u.label}</p>
      <div className="evl-item evl-pair">
        <div className="evl-side">
          <p className="evl-label">The comment</p>
          <Quote span={u.comment} where={`unit-${index}-comment`} onShow={showing.onShow} canShow={showing.canShow} />
        </div>
        <div className="evl-side evl-evidence">
          <p className="evl-label">The reply</p>
          {u.reply ? (
            <Quote span={u.reply} where={`unit-${index}-reply`} onShow={showing.onShow} canShow={showing.canShow} />
          ) : (
            <p className="evl-note">No reply was recognised under this comment.</p>
          )}
        </div>
      </div>
    </>
  );
}

function Strip({ section: s, print, showing }: { section: NarrativeSection; print: boolean; showing: Showing }) {
  const open = s.moves.filter((m) => m.status !== "present");
  const present = s.moves.filter((m) => m.status === "present" && (m.evidence ?? "").trim());
  return (
    <>
      <h3 className="nmap-section-title">
        <span className="nmap-section-label">{s.label}</span>
        <span className="nmap-section-meta muted">
          {movesPhrase(s)} · {s.words.toLocaleString("en-GB")} words
        </span>
      </h3>
      <ol className="nmap-strip" aria-label={`Moves in ${s.label}, in order`}>
        {s.moves.map((m) => (
          <li
            key={m.id}
            className={`nmap-cell nmap-cell-${m.status === "out_of_order" ? "out-of-order" : m.status === "not_detected" ? "not-detected" : m.status}`}
            data-testid="narrative-move"
            data-move={m.id}
            data-status={m.status}
          >
            <span className="nmap-dot" aria-hidden="true" />
            <span className="nmap-cell-label">{m.label}</span>
            {m.status !== "present" ? <span className="nmap-cell-status">{STATUS_WORD[m.status]}</span> : null}
            {print && m.status === "present" ? <span className="nmap-cell-status">present</span> : null}
          </li>
        ))}
      </ol>
      {open.length > 0 || present.length > 0 ? (
        <ul className="nmap-details" aria-label={`The moves of ${s.label}, in detail`}>
          {open.map((m) => (
            <li key={m.id} className="nmap-detail" data-testid="narrative-detail" data-move={m.id} data-status={m.status}>
              <p className="nmap-detail-head">
                <span className="nmap-detail-label">{m.label}</span>{" "}
                <span className="nmap-detail-status">{STATUS_WORD[m.status]}</span>
                {m.note.trim() ? <span className="nmap-detail-note"> {m.note.trim()}</span> : null}
              </p>
              <p className="nmap-question">{m.question}</p>
              {m.plain.trim() ? <p className="nmap-plain">{m.plain}</p> : null}
              {m.frame.trim() ? (
                <figure className="nmap-frame">
                  <blockquote className="nmap-frame-text">{m.frame}</blockquote>
                  <figcaption className="nmap-frame-caption">A frame to fill in; the words are yours.</figcaption>
                </figure>
              ) : null}
              {m.status === "out_of_order" && (m.evidence ?? "").trim() ? <Evidence move={m} print={print} showing={showing} /> : null}
              {print ? null : <LessonDisclosure learnRef={m.learn_ref} />}
              <p className="card-source">
                <span className="card-source-label">Source:</span> <cite>{m.source}</cite>
              </p>
            </li>
          ))}
          {present.map((m) => (
            <li key={m.id} className="nmap-detail nmap-detail-present" data-testid="narrative-present" data-move={m.id}>
              <Evidence move={m} print={print} showing={showing} label />
              {/* An opening sentence taken as this move says so: an assumption, not proof (Codex review N5). */}
              {m.note.trim() ? (
                <p className="nmap-detail-note muted" data-testid="narrative-present-note">
                  {m.note.trim()}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </>
  );
}

/** The writer's own sentence a move rests on: behind a disclosure on screen, open on paper. */
function Evidence({
  move: m,
  print,
  showing,
  label = false,
}: {
  move: NarrativeMove;
  print: boolean;
  showing: Showing;
  label?: boolean;
}) {
  const quote = (
    <>
      <blockquote className="nmap-evidence">
        <q>{(m.evidence ?? "").trim()}</q>
      </blockquote>
      {m.span ? <ShowButton span={m.span} where={`move-${m.id}`} showing={showing} /> : null}
    </>
  );
  if (print) {
    return (
      <>
        {label ? (
          <p className="nmap-detail-head">
            <span className="nmap-detail-label">{m.label}</span> <span className="nmap-detail-status">present</span>
          </p>
        ) : null}
        {quote}
      </>
    );
  }
  return (
    <details className="nmap-sentence">
      <summary className="nmap-sentence-summary">
        {label ? (
          <>
            <span className="nmap-detail-label">{m.label}</span>
            <span className="nmap-sentence-link">Show the sentence</span>
          </>
        ) : (
          <span className="nmap-sentence-link">Show the sentence</span>
        )}
      </summary>
      {quote}
    </details>
  );
}

/**
 * The sentences a missing link concerns, quoted in the serif: behind "Show
 * the sentences" on screen (closed), open on paper. Nothing when there are none.
 */
function LinkEvidence({ link, print, showing, where }: { link: MissingLink; print: boolean; showing: Showing; where: string }) {
  // Placed sentences when the engine sends them (Codex review #3), else the bare quotes.
  const spans = (link.spans ?? []).filter((s) => s.text.trim());
  const list = spans.length > 0 ? spans.map((s) => s.text.trim()) : (link.evidence ?? []).map((s) => s.trim()).filter(Boolean);
  if (list.length === 0) return null;
  const quotes = (
    <ul className="nmap-link-evidence" aria-label="The sentences concerned, quoted from your text">
      {list.map((s, i) => (
        <li key={i} className="nmap-evidence">
          <q>{s}</q>
          {spans[i] ? <ShowButton span={spans[i]!} where={`${where}-${i}`} showing={showing} /> : null}
        </li>
      ))}
    </ul>
  );
  if (print) return quotes;
  return (
    <details className="nmap-sentence" data-testid="narrative-link-evidence">
      <summary className="nmap-sentence-summary">
        <span className="nmap-sentence-link">{list.length === 1 ? "Show the sentence" : "Show the sentences"}</span>
      </summary>
      {quotes}
    </details>
  );
}

/** "Show in text" for a placed sentence, where the surface can show it; nothing on paper. */
function ShowButton({ span, where, showing }: { span: EvidenceSpan; where: string; showing: Showing }) {
  const { onShow, canShow } = showing;
  if (!onShow || (canShow && !canShow(span))) return null;
  const key = showKey(where, span);
  return (
    <p className="evl-meta nmap-show">
      <button
        type="button"
        className="btn-link evl-show"
        data-show-key={key}
        data-testid="show-evidence"
        aria-label={`Show in text: ${shortQuote(span.text)}`}
        onClick={() => onShow(span, key)}
      >
        Show in text
      </button>
    </p>
  );
}

/** One row per section: label, hedges and boosters per 100 words, and the reading word. Every value in text. */
function HedgingTable({ rows }: { rows: readonly HedgingPoint[] }) {
  return (
    <table className="nmap-hedging-table">
      <thead>
        <tr>
          <th scope="col">Section</th>
          <th scope="col" className="nmap-num">
            Hedges
          </th>
          <th scope="col" className="nmap-num">
            Boosters
          </th>
          <th scope="col">Reading</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((h) => (
          <tr key={h.section} data-testid="narrative-hedging-row" data-section={h.section}>
            <th scope="row">{h.label}</th>
            <td className="nmap-num">{per100.format(h.hedges_per_100w)}</td>
            <td className="nmap-num">{per100.format(h.boosters_per_100w)}</td>
            <td>{h.reading}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
