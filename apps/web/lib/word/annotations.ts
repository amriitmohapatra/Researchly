/**
 * Underlines in the Word document (S4d R4): every Office.js call the
 * annotations make, beside lib/word/office.ts and through the same
 * structural `OfficeApi` (so e2e/fake-office.ts stands in for Word).
 *
 * - Annotations need WordApi 1.7 (Word for Microsoft 365: Mac 16.79+,
 *   Windows 2311+, the web); their popup needs 1.8 (Mac 16.85+). A
 *   one-time-purchase Word may report the set and still refuse: the first
 *   insertion is the real test (lib/word/underlines.ts).
 * - Annotations are not saved in the file: they live only in the open
 *   document, and the pane draws them again when it opens.
 * - Every change to a paragraph's underlines is made only after its text is
 *   read again and found to be exactly the text that was checked.
 */
import { annotationColor, POPUP_RESOURCES, snapshotOf, paragraphKey, type SnapshotParagraph, type Underline } from "./live";
import { toWordParagraph, wordApiAtLeast, type OfficeApi, type OfficeCritique, type OfficeParagraph, type WordRequestContext } from "./office";

export interface UnderlineSupport {
  /** WordApi 1.7: underlines can be drawn (if the subscription allows). */
  annotations: boolean;
  /** WordApi 1.8: the underline's popup, with its revisions and Accept/Reject. */
  popups: boolean;
  /** WordApi 1.6: paragraph ids and paragraph change events. */
  paragraphEvents: boolean;
}

export function underlineSupport(api: OfficeApi): UnderlineSupport {
  return {
    annotations: wordApiAtLeast(api, "1.7"),
    popups: wordApiAtLeast(api, "1.8"),
    paragraphEvents: wordApiAtLeast(api, "1.6"),
  };
}

/** The critique Word draws for one underline; the popup's options only where WordApi 1.8 is there. */
export function critiqueOf(u: Underline, popups: boolean): OfficeCritique {
  const c: OfficeCritique = { colorScheme: annotationColor(u.category), start: u.begin, length: u.end - u.begin };
  if (popups) {
    c.popupOptions = {
      brandingTextResourceId: POPUP_RESOURCES.branding,
      titleResourceId: POPUP_RESOURCES.title[u.category],
      subtitleResourceId: POPUP_RESOURCES.subtitle,
      suggestions: u.suggestions,
    };
  }
  return c;
}

const READ_PROPS = "items/text,items/style,items/styleBuiltIn,items/tableNestingLevel";

/** Every body paragraph with its key and nearest heading: one batch, read only. */
export function readSnapshot(api: OfficeApi, keyed: boolean): Promise<SnapshotParagraph[]> {
  return api.Word.run(async (ctx) => {
    const paras = ctx.document.body.paragraphs;
    paras.load(keyed ? `${READ_PROPS},items/uniqueLocalId` : READ_PROPS);
    await ctx.sync();
    return snapshotOf(
      paras.items.map((p) => toWordParagraph(p)),
      paras.items.map((p, i) => paragraphKey(keyed ? p.uniqueLocalId : null, i)),
    );
  });
}

/** One paragraph's underlines to draw: where it was, the text it was checked as, and what to draw. */
export interface PaintItem {
  key: string;
  index: number;
  text: string;
  underlines: Underline[];
}

export interface PaintResult {
  /** Per painted paragraph: suggestion id → annotation id. */
  painted: Map<string, Map<string, string>>;
  /** Paragraphs whose text changed since the check (or that are gone): left alone. */
  skipped: string[];
  /** Annotation ids that were deleted (ours, in the painted paragraphs). */
  removed: string[];
  /** Word refused to insert: "insert" (the annotations API itself), or "word" (anything else). */
  failure: "insert" | "word" | null;
}

function locate(items: readonly OfficeParagraph[], keyed: boolean, key: string, index: number): OfficeParagraph | null {
  if (keyed) return items.find((p, i) => paragraphKey(p.uniqueLocalId, i) === key) ?? null;
  return items[index] ?? null;
}

/**
 * Replace our underlines in each paragraph with new ones. A paragraph is
 * touched only when its text still reads exactly as checked. Old ones go
 * first (in their own sync), so a refused insertion never leaves two sets.
 * Never throws.
 */
export async function paintParagraphs(
  api: OfficeApi,
  items: readonly PaintItem[],
  opts: { keyed: boolean; popups: boolean; ours: ReadonlySet<string> },
): Promise<PaintResult> {
  const result: PaintResult = { painted: new Map(), skipped: [], removed: [], failure: null };
  if (items.length === 0) return result;
  try {
    await api.Word.run(async (ctx) => {
      const paras = ctx.document.body.paragraphs;
      paras.load(opts.keyed ? "items/text,items/uniqueLocalId" : "items/text");
      await ctx.sync();
      const targets: { item: PaintItem; para: OfficeParagraph }[] = [];
      for (const item of items) {
        const para = locate(paras.items, opts.keyed, item.key, item.index);
        if (!para || para.text !== item.text || !para.getAnnotations || !para.insertAnnotations) result.skipped.push(item.key);
        else targets.push({ item, para });
      }
      if (targets.length === 0) return;
      const existing = targets.map((t) => {
        const c = t.para.getAnnotations!();
        c.load("items/id");
        return c;
      });
      await ctx.sync();
      for (const c of existing) {
        for (const a of c.items) {
          if (opts.ours.has(a.id)) {
            a.delete();
            result.removed.push(a.id);
          }
        }
      }
      await ctx.sync();
      const inserted: { item: PaintItem; ids: { value: string[] } }[] = [];
      for (const t of targets) {
        if (t.item.underlines.length === 0) {
          result.painted.set(t.item.key, new Map());
          continue;
        }
        inserted.push({ item: t.item, ids: t.para.insertAnnotations!({ critiques: t.item.underlines.map((u) => critiqueOf(u, opts.popups)) }) });
      }
      if (inserted.length === 0) return;
      try {
        await ctx.sync();
      } catch {
        result.failure = "insert";
        return;
      }
      for (const { item, ids } of inserted) {
        const map = new Map<string, string>();
        item.underlines.forEach((u, i) => {
          const id = ids.value?.[i];
          if (typeof id === "string" && id) map.set(u.id, id);
        });
        result.painted.set(item.key, map);
      }
    });
  } catch {
    if (!result.failure) result.failure = "word";
  }
  return result;
}

/** Remove every underline of ours in the document (switched off, a new full check). Never throws; false when Word refused. */
export async function clearUnderlines(api: OfficeApi, ours: ReadonlySet<string>): Promise<boolean> {
  if (ours.size === 0) return true;
  try {
    return await api.Word.run(async (ctx) => {
      const paras = ctx.document.body.paragraphs;
      paras.load("items/text");
      await ctx.sync();
      const lists = paras.items.map((p) => {
        const c = p.getAnnotations?.();
        c?.load("items/id");
        return c;
      });
      await ctx.sync();
      for (const c of lists) for (const a of c?.items ?? []) if (ours.has(a.id)) a.delete();
      await ctx.sync();
      return true;
    });
  } catch {
    return false;
  }
}

type AnnotationAct = "accept" | "reject" | "delete";

/** Accept, reject or delete one underline. Never throws; false when Word refused or it is gone. */
export async function actOnAnnotation(api: OfficeApi, id: string, act: AnnotationAct): Promise<boolean> {
  try {
    return await api.Word.run(async (ctx) => {
      const a = ctx.document.getAnnotationById?.(id);
      if (!a) return false;
      if (act === "accept") a.critiqueAnnotation.accept();
      else if (act === "reject") a.critiqueAnnotation.reject();
      else a.delete();
      await ctx.sync();
      return true;
    });
  } catch {
    return false;
  }
}

/** The paragraph's text now (for "did Word already apply it?"), or null when it cannot be read. */
export async function readParagraphText(api: OfficeApi, key: string, index: number, keyed: boolean): Promise<string | null> {
  try {
    return await api.Word.run(async (ctx: WordRequestContext) => {
      const paras = ctx.document.body.paragraphs;
      paras.load(keyed ? "items/text,items/uniqueLocalId" : "items/text");
      await ctx.sync();
      return locate(paras.items, keyed, key, index)?.text ?? null;
    });
  } catch {
    return null;
  }
}

export interface AnnotationHandlers {
  onClick(id: string): void;
  onHover(id: string): void;
  onPopup(id: string, action: string, suggestion: string | null): void;
  /** Something in the document may have changed (a paragraph event, or a moved selection). */
  onEdit(): void;
}

/**
 * Listen to Word: clicks and hovers on underlines (1.7), the popup's
 * Accept and Reject (1.8), and edits: paragraph events where Word has them
 * (1.6), else the selection moving (every keystroke moves it). Never throws;
 * returns which listeners are on.
 */
export async function listen(
  api: OfficeApi,
  support: UnderlineSupport,
  h: AnnotationHandlers,
): Promise<{ annotations: boolean; edits: "paragraphs" | "selection" | "none" }> {
  let annotations = false;
  let edits: "paragraphs" | "selection" | "none" = "none";
  try {
    await api.Word.run(async (ctx) => {
      const doc = ctx.document;
      if (support.annotations && doc.onAnnotationClicked && doc.onAnnotationHovered) {
        doc.onAnnotationClicked.add((a) => h.onClick(a.id));
        doc.onAnnotationHovered.add((a) => h.onHover(a.id));
        if (support.popups && doc.onAnnotationPopupAction) {
          doc.onAnnotationPopupAction.add((a) => h.onPopup(a.id, a.action, a.critiqueSuggestion ?? null));
        }
        annotations = true;
      }
      if (support.paragraphEvents && doc.onParagraphChanged && doc.onParagraphAdded && doc.onParagraphDeleted) {
        doc.onParagraphChanged.add(() => h.onEdit());
        doc.onParagraphAdded.add(() => h.onEdit());
        doc.onParagraphDeleted.add(() => h.onEdit());
        edits = "paragraphs";
      }
      await ctx.sync();
    });
  } catch {
    edits = "none";
  }
  if (edits === "none") {
    const office = api.Office;
    const type = office.EventType?.DocumentSelectionChanged;
    try {
      if (type && office.context.document?.addHandlerAsync) {
        office.context.document.addHandlerAsync(type, () => h.onEdit());
        edits = "selection";
      }
    } catch {
      /* no edit events at all: underlines follow the full check only */
    }
  }
  return { annotations, edits };
}
