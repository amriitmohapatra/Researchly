import { type CheckStatus, stateDescription, stateLabel, stateLook } from "@/lib/check-state";

/**
 * One look per state (S4d R2; DESIGN.md "The six states"): nothing for
 * hidden, a ring while checking (still under reduced motion), a count
 * badge for issues, a tick for clear, a small warning sign for partial and
 * a crossed-out mark for offline. Colours from the design tokens. The
 * label is always in the accessibility tree (a polite status region); pass
 * `showLabel={false}` where only the mark fits, as on a widget.
 */
export function StatusMark({ status, showLabel = true }: { status: CheckStatus; showLabel?: boolean }) {
  const look = stateLook(status.state);
  const label = stateLabel(status);
  const description = stateDescription(status);
  const detail = description.startsWith(label) ? description.slice(label.length).replace(/^\.\s*/, "") : description;
  return (
    <span
      className={`status-mark status-${status.state}`}
      data-state={status.state}
      data-testid="status-mark"
      role="status"
      aria-live="polite"
      aria-atomic="true"
      title={look === "none" ? undefined : description}
    >
      {look !== "none" && <Mark look={look} count={status.count} />}
      <span className={showLabel && look !== "none" ? "status-mark-label" : "sr-only"}>{label}</span>
      {detail && <span className="sr-only"> {detail}</span>}
    </span>
  );
}

function Mark({ look, count }: { look: ReturnType<typeof stateLook>; count: number }) {
  const svg = { width: 20, height: 20, viewBox: "0 0 20 20", "aria-hidden": true, focusable: false } as const;
  switch (look) {
    case "ring":
      return (
        <svg {...svg} className="sm-svg">
          <circle className="sm-track" cx="10" cy="10" r="7" fill="none" strokeWidth="2" />
          <circle className="sm-ring status-spin" cx="10" cy="10" r="7" fill="none" strokeWidth="2" strokeDasharray="16 28" strokeLinecap="round" />
        </svg>
      );
    case "badge":
      return (
        <svg {...svg} className="sm-svg">
          <circle className="sm-badge" cx="10" cy="10" r="9" />
          <text className="sm-badge-text" x="10" y="10" textAnchor="middle" dominantBaseline="central">
            {count > 99 ? "99+" : count}
          </text>
        </svg>
      );
    case "tick":
      return (
        <svg {...svg} className="sm-svg">
          <circle className="sm-mark" cx="10" cy="10" r="7" fill="none" strokeWidth="1.6" />
          <path className="sm-mark" d="M6.6 10.2l2.2 2.2 4.6-4.8" fill="none" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "warning":
      return (
        <svg {...svg} className="sm-svg">
          <circle className="sm-mark" cx="9" cy="9" r="6.5" fill="none" strokeWidth="1.6" />
          <path className="sm-warning" d="M15 10.5l4.5 8h-9z" />
          <path className="sm-warning-glyph" d="M15 13.3v2.2M15 17.1v.1" fill="none" strokeWidth="1.3" strokeLinecap="round" />
        </svg>
      );
    case "crossed":
      return (
        <svg {...svg} className="sm-svg">
          <circle className="sm-offline" cx="10" cy="10" r="7" fill="none" strokeWidth="1.6" />
          <path className="sm-offline" d="M4 16L16 4" fill="none" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      );
    default:
      return null;
  }
}
