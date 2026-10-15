/**
 * A fake Office.js for tests: the slice of the Word API the taskpane uses
 * (lib/word/office.ts), over an in-memory document.
 *
 * One implementation serves both suites:
 * - e2e: `fakeOfficeScript()` is served in place of Microsoft's office.js by
 *   page.route, so the page loads it exactly as it loads the real one (and
 *   the route's CSP must allow it);
 * - unit: `installFakeOffice({}, config)` builds the globals in Node.
 *
 * `installFakeOffice` must stay self-contained (no imports, no outer
 * variables): it is sent to the browser as its own source text.
 *
 * Faithful where it matters:
 * - changes are queued and applied at `context.sync()`;
 * - setting `changeTrackingMode` without WordApi 1.4 does not throw, it
 *   fails the whole batch at sync and nothing in it is applied (the bug that
 *   once silently killed every Apply in the old add-in);
 * - `search` finds non-overlapping matches, left to right, like Word;
 * - table cells (WordApi 1.3) report rowIndex, cellIndex and the row's
 *   cellCount only after `context.sync()`, and are null objects for a table
 *   paragraph the fake was given no cell for.
 * - annotations (S4d R4, WordApi 1.7; popups 1.8): inserted, read, deleted,
 *   accepted and rejected at sync; a range outside the paragraph, or
 *   popupOptions without 1.8, fails the batch as Word does. Paragraph ids
 *   and paragraph events need 1.6; without them, edits are reported as
 *   selection changes only. Tests act as the writer through `__fakeWordType`,
 *   `__fakeWordClick`, `__fakeWordHover` and `__fakeWordPopup`.
 */

export interface FakeParagraph {
  text: string;
  style?: string;
  styleBuiltIn?: string;
  tableNestingLevel?: number;
  /**
   * Where a table paragraph's cell sits, as Word 1.3 reports it: `rowIndex`
   * and `cellIndex` (cells along the row) and its row's `cellCount`. Left
   * out on a table paragraph: Word gives a null object (an unplaceable cell).
   */
  cell?: { rowIndex: number; cellIndex: number; cellCount: number };
  /** Word's paragraph id (assigned by the fake; exposed as `uniqueLocalId` with WordApi 1.6). */
  uid?: string;
}

/** An underline in the fake document (WordApi 1.7). */
export interface FakeAnnotation {
  id: string;
  /** The paragraph's uid. */
  paragraph: string;
  start: number;
  length: number;
  /** The text under it when it was drawn. */
  text: string;
  colorScheme: string;
  /** The popup's resources and revisions (WordApi 1.8), or null without them. */
  popup: { branding: string; title: string; subtitle: string; suggestions: string[] } | null;
  state: "Created" | "Accepted" | "Rejected";
}

export interface FakeWordConfig {
  paragraphs: FakeParagraph[];
  /** Office.onReady's host; null = opened outside Office. Default "Word". */
  host?: string | null;
  /** WordApi 1.4 (tracked changes, fields). Default true. */
  api14?: boolean;
  /** WordApi 1.3 (table cells). Default true; false also means no 1.4. */
  api13?: boolean;
  /** WordApi 1.6 (paragraph ids and events). Default false. */
  api16?: boolean;
  /** WordApi 1.7 (annotations: underlines). Default false. */
  api17?: boolean;
  /** WordApi 1.8 (the annotation popup). Default false. */
  api18?: boolean;
  /** Word applies a popup's chosen revision itself on Accept (default: it only reports it). */
  popupAppliesText?: boolean;
  /** The writer's Track Changes setting before any apply. Default "Off". */
  trackingMode?: string;
  /** Paragraph indexes whose ranges sit inside a Word field (a citation). */
  fieldParagraphs?: number[];
  /** Mimic office.js removing history.pushState/replaceState. */
  nullHistory?: boolean;
  /** Where the cursor is when the pane opens: a paragraph index (default 0). */
  cursor?: number;
  /**
   * Host failures to reproduce (Codex review R3), each at `context.sync()`
   * like a real Word error:
   * - `fields`: loading a range's fields fails;
   * - `insert`: "before" fails the insertion with nothing changed, "after"
   *   makes the change and then reports an error (a batch that partly ran);
   * - `select`: selecting a range fails;
   * - `restoreTracking`: switching Track Changes back off (any mode other
   *   than TrackAll) fails;
   * - `cells`: loading a table cell's place fails.
   */
  failures?: {
    fields?: boolean;
    insert?: "before" | "after";
    select?: boolean;
    restoreTracking?: boolean;
    cells?: boolean;
    /** `insert`: every insertAnnotations fails (a Word without Microsoft 365); `popup`: only those with popupOptions. */
    annotations?: "insert" | "popup";
  };
}

export interface FakeEdit {
  paragraph: number;
  start: number;
  end: number;
  before: string;
  text: string;
  tracked: boolean;
}

export interface FakeWordState {
  paragraphs: FakeParagraph[];
  selection: { paragraph: number; start: number; end: number; text: string } | null;
  trackingMode: string;
  edits: FakeEdit[];
  failedBatches: number;
  /** Every changeTrackingMode assignment, in order. */
  trackingWrites: string[];
  /** Underlines in the document (WordApi 1.7). */
  annotations: FakeAnnotation[];
  /** insertAnnotations batches that failed. */
  failedAnnotationInserts: number;
}

/* eslint-disable @typescript-eslint/no-explicit-any */
export function installFakeOffice(target: any, config: FakeWordConfig): FakeWordState {
  const api13 = config.api13 !== false;
  const api14 = api13 && config.api14 !== false;
  const api16 = api14 && config.api16 === true;
  const api17 = api14 && config.api17 === true;
  const api18 = api17 && config.api18 === true;
  const failures = config.failures ?? {};
  let uidCounter = 0;
  const newUid = () => "{0000" + (++uidCounter).toString(16).padStart(4, "0") + "-FA4E-4D0C-9A11-" + String(uidCounter).padStart(12, "0") + "}";
  let annotationCounter = 0;
  const state: FakeWordState = {
    paragraphs: config.paragraphs.map((p) => ({ ...p, uid: newUid() })),
    selection: null,
    trackingMode: config.trackingMode ?? "Off",
    edits: [],
    failedBatches: 0,
    trackingWrites: [],
    annotations: [],
    failedAnnotationInserts: 0,
  };
  // Word's event handlers, by event (held here: functions are not part of the state).
  const handlers: Record<string, ((args: any) => unknown)[]> = {
    clicked: [],
    hovered: [],
    popup: [],
    paragraphChanged: [],
    paragraphAdded: [],
    paragraphDeleted: [],
    selection: [],
  };
  const fire = (name: string, args: unknown) => {
    for (const h of handlers[name] ?? []) setTimeout(() => void h(args), 0);
  };
  const source = (name: string) => ({
    add(h: (args: any) => unknown) {
      handlers[name]!.push(h);
      return { remove() {} };
    },
  });
  target.__fakeWord = state;
  if (config.nullHistory && target.history) {
    target.history.pushState = null;
    target.history.replaceState = null;
  }

  function versionAtMost(v: string | undefined, max: string): boolean {
    const a = (v ?? "1.1").split(".").map(Number);
    const b = max.split(".").map(Number);
    for (let i = 0; i < 2; i++) {
      if ((a[i] ?? 0) !== (b[i] ?? 0)) return (a[i] ?? 0) < (b[i] ?? 0);
    }
    return true;
  }

  function run(batch: (ctx: any) => Promise<any>) {
    let ops: (() => void)[] = [];
    let poisoned = false;

    // A range inside one paragraph; `endPi` > pi only for a range made by expandTo.
    function makeRange(pi: number, start: number, end: number, endPi: number = pi) {
      const r: any = {
        pi,
        start,
        end,
        endPi,
        text: state.paragraphs[pi]!.text.slice(start, end),
        load() {
          r.text = state.paragraphs[r.pi]!.text.slice(r.start, r.end);
        },
        getRange(where?: string) {
          if (where === "End") return makeRange(r.endPi, r.end, r.end);
          if (where === "Start") return makeRange(r.pi, r.start, r.start);
          return makeRange(r.pi, r.start, r.end, r.endPi);
        },
        expandTo(other: any) {
          const first = other.pi < r.pi || (other.pi === r.pi && other.start < r.start) ? other : r;
          const last = other.endPi > r.endPi || (other.endPi === r.endPi && other.end > r.end) ? other : r;
          return makeRange(first.pi, first.start, last.end, last.endPi);
        },
        get paragraphs() {
          const items: any[] = [];
          for (let i = r.pi; i <= r.endPi; i++) items.push(makeParagraph(i));
          return { items, load() {} };
        },
        select() {
          ops.push(() => {
            if (failures.select) throw new Error("GeneralException: the selection could not be made");
            state.selection = { paragraph: r.pi, start: r.start, end: r.end, text: state.paragraphs[r.pi]!.text.slice(r.start, r.end) };
          });
        },
        insertText(text: string, where: string) {
          if (where !== "Replace") throw new Error(`fake office: unsupported insert location ${where}`);
          ops.push(() => {
            if (failures.insert === "before") throw new Error("GeneralException: the text could not be inserted");
            const p = state.paragraphs[r.pi]!;
            const before = p.text.slice(r.start, r.end);
            p.text = p.text.slice(0, r.start) + text + p.text.slice(r.end);
            // Word takes an underline away with the words under it.
            state.annotations = state.annotations.filter(
              (a) => a.paragraph !== p.uid || a.start + a.length <= r.start || a.start >= r.end,
            );
            // Like any edit, it is reported (paragraph events with 1.6; the selection moves).
            if (api16) fire("paragraphChanged", { type: "Changed", uniqueLocalIds: [p.uid] });
            fire("selection", { type: "documentSelectionChanged" });
            state.edits.push({ paragraph: r.pi, start: r.start, end: r.end, before, text, tracked: state.trackingMode === "TrackAll" });
            r.end = r.start + text.length;
            r.text = text;
            if (failures.insert === "after") throw new Error("GeneralException: an error after the insertion");
          });
          return r;
        },
      };
      if (api14) {
        const inField = (config.fieldParagraphs ?? []).includes(pi);
        r.fields = {
          items: inField ? [{ code: "ADDIN ZOTERO_ITEM" }] : [],
          load() {
            if (failures.fields) {
              ops.push(() => {
                throw new Error("GeneralException: the fields could not be read");
              });
            }
          },
        };
      }
      return r;
    }

    // A table cell, WordApi 1.3: its numbers arrive at sync, like any loaded property.
    function makeCell(p: FakeParagraph) {
      const place = (p.tableNestingLevel ?? 0) > 0 ? p.cell : undefined;
      const row: any = {
        load() {
          ops.push(() => {
            row.cellCount = place!.cellCount;
          });
        },
      };
      const cell: any = {
        isNullObject: undefined,
        parentRow: row,
        load() {
          ops.push(() => {
            if (failures.cells) throw new Error("GeneralException: the table cell could not be read");
            cell.isNullObject = !place;
            if (place) {
              cell.rowIndex = place.rowIndex;
              cell.cellIndex = place.cellIndex;
            }
          });
        },
      };
      return cell;
    }

    // An annotation proxy (WordApi 1.7): its actions run at sync, and fail there if it is gone.
    function makeAnnotation(id: string) {
      const find = () => {
        const a = state.annotations.find((x) => x.id === id);
        if (!a) throw new Error("ItemNotFound: the annotation does not exist");
        return a;
      };
      const current = state.annotations.find((x) => x.id === id);
      return {
        id,
        state: current?.state,
        critiqueAnnotation: {
          accept() {
            ops.push(() => {
              find().state = "Accepted";
            });
          },
          reject() {
            ops.push(() => {
              find().state = "Rejected";
            });
          },
        },
        delete() {
          ops.push(() => {
            find();
            state.annotations = state.annotations.filter((x) => x.id !== id);
          });
        },
        load() {},
      };
    }

    function makeParagraph(pi: number) {
      const p: FakeParagraph = state.paragraphs[pi]!;
      const para: any = {
        text: p.text,
        style: p.style ?? "Normal",
        styleBuiltIn: p.styleBuiltIn ?? "Other",
        tableNestingLevel: p.tableNestingLevel ?? 0,
        search(needle: string, options: { matchCase?: boolean }) {
          const hay = options?.matchCase ? p.text : p.text.toLowerCase();
          const n = options?.matchCase ? needle : needle.toLowerCase();
          const items: any[] = [];
          if (n) for (let i = hay.indexOf(n); i >= 0; i = hay.indexOf(n, i + n.length)) items.push(makeRange(pi, i, i + n.length));
          return { items, load() {} };
        },
      };
      // Older Word has no table-cell API at all.
      if (api13) {
        Object.defineProperty(para, "parentTableCellOrNullObject", { get: () => makeCell(p), enumerable: true });
      }
      if (api16) para.uniqueLocalId = p.uid;
      if (api17) {
        para.insertAnnotations = (set: { critiques: any[] }) => {
          const result: { value: any } = { value: undefined };
          ops.push(() => {
            const withPopup = set.critiques.some((c) => c.popupOptions);
            if (failures.annotations === "insert" || (failures.annotations === "popup" && withPopup)) {
              state.failedAnnotationInserts++;
              throw new Error("GeneralException: annotations are not available");
            }
            if (withPopup && !api18) {
              state.failedAnnotationInserts++;
              throw new Error("InvalidArgument: popupOptions");
            }
            for (const c of set.critiques) {
              if (!(c.start >= 0 && c.length > 0 && c.start + c.length <= p.text.length)) {
                state.failedAnnotationInserts++;
                throw new Error("InvalidArgument: the critique is outside the paragraph");
              }
            }
            result.value = set.critiques.map((c) => {
              const id = "ann-" + ++annotationCounter;
              const o = c.popupOptions;
              state.annotations.push({
                id,
                paragraph: p.uid!,
                start: c.start,
                length: c.length,
                text: p.text.slice(c.start, c.start + c.length),
                colorScheme: c.colorScheme,
                popup: o
                  ? { branding: o.brandingTextResourceId, title: o.titleResourceId, subtitle: o.subtitleResourceId, suggestions: [...o.suggestions] }
                  : null,
                state: "Created",
              });
              return id;
            });
          });
          return result;
        };
        para.getAnnotations = () => {
          const coll: any = {
            items: [],
            load() {
              ops.push(() => {
                coll.items = state.annotations.filter((a) => a.paragraph === p.uid).map((a) => makeAnnotation(a.id));
              });
            },
          };
          return coll;
        };
      }
      return para;
    }

    const paragraphs = {
      items: state.paragraphs.map((_p, i) => makeParagraph(i)),
      load() {
        paragraphs.items = state.paragraphs.map((_p, i) => makeParagraph(i));
      },
    };

    const document: any = {
      body: {
        paragraphs,
        getRange(where?: string) {
          const last = state.paragraphs.length - 1;
          if (where === "Start") return makeRange(0, 0, 0);
          if (where === "End") return makeRange(last, state.paragraphs[last]!.text.length, state.paragraphs[last]!.text.length);
          return makeRange(0, 0, state.paragraphs[last]!.text.length, last);
        },
      },
      load() {},
      getSelection() {
        const sel = state.selection;
        if (sel) return makeRange(sel.paragraph, sel.start, sel.end);
        const pi = Math.min(Math.max(config.cursor ?? 0, 0), state.paragraphs.length - 1);
        return makeRange(pi, 0, 0);
      },
    };
    if (api16) {
      document.onParagraphChanged = source("paragraphChanged");
      document.onParagraphAdded = source("paragraphAdded");
      document.onParagraphDeleted = source("paragraphDeleted");
    }
    if (api17) {
      document.getAnnotationById = (id: string) => makeAnnotation(id);
      document.onAnnotationClicked = source("clicked");
      document.onAnnotationHovered = source("hovered");
    }
    if (api18) document.onAnnotationPopupAction = source("popup");
    Object.defineProperty(document, "changeTrackingMode", {
      get: () => state.trackingMode,
      set: (mode: string) => {
        state.trackingWrites.push(mode);
        if (!api14) {
          poisoned = true; // no error now: the batch fails at sync
          return;
        }
        ops.push(() => {
          if (failures.restoreTracking && mode !== "TrackAll") throw new Error("GeneralException: Track Changes could not be set");
          state.trackingMode = mode;
        });
      },
    });

    const ctx = {
      document,
      async sync() {
        const pending = ops;
        ops = [];
        if (poisoned) {
          poisoned = false;
          state.failedBatches++;
          throw new Error("GeneralException: the requested operation is not supported in this Word version");
        }
        for (const op of pending) op();
      },
    };
    return Promise.resolve().then(() => batch(ctx));
  }

  const host = config.host === undefined ? "Word" : config.host;
  target.Office = {
    HostType: { Word: "Word" },
    onReady(cb?: (info: { host: string | null; platform: string | null }) => void) {
      // Like office.js: the host's scripts (and so `Word`) arrive
      // asynchronously, and only inside Word, before onReady resolves.
      return new Promise((resolve) => setTimeout(resolve, 20)).then(() => {
        if (host === "Word") target.Word = wordNamespace;
        const info = { host, platform: host ? "PC" : null };
        if (cb) cb(info);
        return info;
      });
    },
    EventType: { DocumentSelectionChanged: "documentSelectionChanged" },
    context: {
      document: {
        addHandlerAsync(type: string, h: () => void) {
          if (type === "documentSelectionChanged") handlers.selection!.push(h);
        },
      },
      requirements: {
        isSetSupported(name: string, version?: string) {
          if (name !== "WordApi") return false;
          return versionAtMost(version, api18 ? "1.8" : api17 ? "1.7" : api16 ? "1.6" : api14 ? "1.4" : api13 ? "1.3" : "1.2");
        },
      },
    },
  };
  const wordNamespace = {
    run,
    InsertLocation: { replace: "Replace" },
    ChangeTrackingMode: { off: "Off", trackAll: "TrackAll", trackMineOnly: "TrackMineOnly" },
  };
  // For unit tests that act after start-up: Word as it is once ready.
  target.__fakeWordNamespace = wordNamespace;

  /* ---------- the writer, for tests ---------- */

  /** The writer changes paragraph `pi` to `text` (Word reports it as 1.6 paragraph events, and the selection moves). */
  target.__fakeWordType = (pi: number, text: string) => {
    const p = state.paragraphs[pi]!;
    p.text = text;
    // Word takes an underline away when the words under it change (shifting is not modelled: those go too).
    state.annotations = state.annotations.filter((a) => a.paragraph !== p.uid || text.slice(a.start, a.start + a.length) === a.text);
    fire("paragraphChanged", { type: "Changed", uniqueLocalIds: [p.uid] });
    fire("selection", { type: "documentSelectionChanged" });
  };
  /** The writer adds a paragraph after `pi`. */
  target.__fakeWordAddParagraph = (pi: number, text: string, styleBuiltIn = "Normal") => {
    const p: FakeParagraph = { text, styleBuiltIn, uid: newUid() };
    state.paragraphs.splice(pi + 1, 0, p);
    fire("paragraphAdded", { type: "Added", uniqueLocalIds: [p.uid] });
    fire("selection", { type: "documentSelectionChanged" });
  };
  target.__fakeWordClick = (id: string) => fire("clicked", { id });
  target.__fakeWordHover = (id: string) => fire("hovered", { id });
  /** The writer chooses Accept (with a revision) or Reject in an underline's popup. */
  target.__fakeWordPopup = (id: string, action: "Accept" | "Reject", suggestion?: string) => {
    const a = state.annotations.find((x) => x.id === id);
    if (!a) return;
    a.state = action === "Accept" ? "Accepted" : "Rejected";
    if (action === "Accept" && suggestion !== undefined && config.popupAppliesText) {
      const p = state.paragraphs.find((x) => x.uid === a.paragraph)!;
      p.text = p.text.slice(0, a.start) + suggestion + p.text.slice(a.start + a.length);
      state.annotations = state.annotations.filter((x) => x.id !== id);
    }
    fire("popup", { id, action, critiqueSuggestion: action === "Accept" ? suggestion : undefined });
  };
  return state;
}
/* eslint-enable @typescript-eslint/no-explicit-any */

/** The fake as an office.js response body: it reads its config from `window.__fakeWordConfig`. */
export function fakeOfficeScript(): string {
  return `(${installFakeOffice.toString()})(window, window.__fakeWordConfig || { paragraphs: [] });`;
}
