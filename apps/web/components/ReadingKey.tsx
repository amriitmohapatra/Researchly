import type { Category } from "@researchly/contract";
import { CATEGORIES, CATEGORY_ORDER } from "@/lib/categories";
import { CategoryIcon } from "./CategoryIcon";

/**
 * "How to read the feedback": the four-type taxonomy taught before the first
 * check, with live specimens of each underline style (CLAUDE.md #3).
 * Colour is never the only cue: each row has the label, icon and underline.
 */
const SPECIMENS: Record<Category, { before: string; flagged: string; after: string; note: string }> = {
  correction: { before: "to understand ", flagged: "the the", after: " dynamics", note: "Likely an error. Worth fixing." },
  improvement: { before: "", flagged: "In order to", after: " fit the model", note: "Correct, but clearer if revised." },
  convention: {
    before: "a ",
    flagged: "seven day window",
    after: "",
    note: "A norm of research writing. Never an error; follow it if your journal does.",
  },
  preference: { before: "we ", flagged: "utilize", after: " daily counts", note: "A matter of taste. Hidden unless you switch it on." },
};

export function ReadingKey({ className, onExample }: { className?: string; onExample?: () => void }) {
  return (
    <section className={`key${className ? ` ${className}` : ""}`} aria-labelledby="key-title" data-testid="reading-key">
      <h2 id="key-title" className="key-title">
        How to read the feedback
      </h2>
      <ul className="key-list">
        {CATEGORY_ORDER.map((c) => {
          const s = SPECIMENS[c];
          return (
            <li key={c} className={`key-row key-${c}`}>
              <p className="key-label">
                <CategoryIcon category={c} />
                {CATEGORIES[c].label}
              </p>
              <p className="key-specimen" aria-hidden="true">
                {s.before}
                <span className={`spec spec-${c}`}>{s.flagged}</span>
                {s.after}
              </p>
              <p className="key-note">{s.note}</p>
            </li>
          );
        })}
      </ul>
      <p className="key-foot">
        Every suggestion says why and names its source. Advice follows the section, so passive voice is never flagged in
        Methods. Nothing is rewritten for you.
      </p>
      {onExample ? (
        <button type="button" className="btn btn-secondary key-example" onClick={onExample} data-testid="insert-example">
          Insert an example draft
        </button>
      ) : null}
    </section>
  );
}
