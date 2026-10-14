import { formatRate, sparkPath, sparkPoints } from "@/lib/progress-view";

const W = 132;
const H = 36;

/**
 * One rule's line (S4c progress): flags per 1,000 words in each recorded
 * check, oldest on the left, from zero at the bottom to the line's own
 * highest value. A check that did not assess the rule breaks the line and
 * shows a small hollow mark on the baseline (never a zero). One series,
 * one hue (the accent), a 2px line, a hairline
 * baseline, and an end dot with a surface ring marking the latest check.
 * Every point has a hit area larger than the mark with its value as a
 * native tooltip; the same values are written out in the page's table, so
 * nothing depends on hovering. Decorative to assistive technology beyond
 * its one-sentence label: the numbers beside it carry the reading.
 */
export function Sparkline({ rates, label }: { rates: readonly (number | null)[]; label: string }) {
  const pts = sparkPoints(rates, W, H);
  const assessed = pts.filter((p) => p.y !== null);
  const last = assessed[assessed.length - 1];
  const path = sparkPath(pts);
  return (
    <svg className="spark" width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} data-testid="sparkline">
      <line className="spark-base" x1={0} x2={W} y1={H - 4} y2={H - 4} />
      {path && assessed.length > 1 ? <path className="spark-line" d={path} /> : null}
      {pts.map((p, i) =>
        p.y === null ? (
          // Not assessed in this check (Codex review N2): a hollow mark on the baseline, never a zero on the line.
          <g key={i} data-testid="spark-gap">
            <circle className="spark-gap" cx={p.x} cy={H - 4} r={2.5} />
            <circle className="spark-hit" cx={p.x} cy={H - 4} r={8}>
              <title>{`Check ${i + 1}: not assessed`}</title>
            </circle>
          </g>
        ) : (
          <g key={i}>
            {/* A point with gaps on both sides has no line to sit on: give it a mark of its own. */}
            {pts[i - 1]?.y == null && pts[i + 1]?.y == null && p !== last ? (
              <circle className="spark-dot" cx={p.x} cy={p.y} r={2.5} />
            ) : null}
            <circle className="spark-hit" cx={p.x} cy={p.y} r={8}>
              <title>{`Check ${i + 1}: ${formatRate(rates[i] ?? 0)} per 1,000 words`}</title>
            </circle>
          </g>
        ),
      )}
      {last && last.y !== null ? <circle className="spark-end" cx={last.x} cy={last.y} r={4} /> : null}
    </svg>
  );
}
