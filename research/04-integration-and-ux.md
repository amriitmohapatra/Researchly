# Landscape Research 04 — Integration Surfaces & Interaction Patterns

*Researchly project · Landscape research phase · Compiled 2026-08-10.*
*Focus: how writing assistants technically reach writers, and which interaction patterns work. Sources at the end.*

---

## 1. How Grammarly-class tools technically integrate

**Browser extension (the canonical surface).** Grammarly's extension injects content scripts that observe `<textarea>` and `contenteditable` fields across ~2 billion sites. Their engineering blog documents a key architectural evolution: they originally *wrapped error text in DOM nodes* to style underlines — which polluted host-page DOMs, corrupted rich-editor state, and got them actively blocked by ProseMirror/Quill/Draft.js-based editors. The current architecture is a **non-invasive overlay**: `Range.getClientRects()` computes pixel coordinates of flagged spans, and underlines are drawn in a separate absolutely-positioned container (in a shadow DOM for style isolation) on top of the field — the text field's DOM is never touched. Costs: naive `getBoundingClientRect()`/`getComputedStyle()` polling "can easily consume over 90% of CPU," so they use relative positioning, recompute only on text change, viewport culling, and ~1s fallback polling. Trade-off: occasional pixel misalignment in exchange for universal compatibility.

**Grammarly Text Editor SDK: dead.** After GA in 2022, Grammarly announced shutdown in July 2023; the SDK was **deprecated January 10, 2024**. Sapling and WProofreader now market drop-in replacement SDKs. Lessons: there is currently no first-party "embed Grammarly" option; a small third-party SDK market fills the gap (evidence that an embeddable checking API is a viable niche); platform dependence on someone else's SDK is risky.

**Word add-ins (Office JS).** A supported, cross-platform (Windows/Mac/web) surface. Crucially for academic workflows, the Word JS API exposes **tracked changes** (`Word.TrackedChange`, `TrackedChangeCollection`, `ChangeTrackingMode`) — an add-in can write edits as revisions the author accepts/rejects natively. Paperpal's Word add-in is the exemplar: sidebar taskpane, real-time suggestions, inside the researcher's native .docx/track-changes workflow. (Office JS text replacement is range-based and can conflict with user edits — a known friction Paperpal documents.)

**Google Docs: the hostile surface.** Workspace add-ons/Apps Script can read/edit documents and add comments, but the Docs API **cannot create suggestion-mode edits** (long-standing open issue 287903901). The state-of-the-art workaround (Bromberg's interface0) drives a cloud headless browser logged in as a bot account — fragile by design. Grammarly reaches Docs via its extension overlay, not the API. Takeaway: reaching Docs properly requires the browser-extension overlay; the add-on API alone limits you to sidebar + comments.

**Desktop overlay apps / mobile keyboards.** Grammarly desktop hooks system text via accessibility APIs with a floating widget; documented issues with overlap and silent failures per app. Mobile = custom keyboards (rewrite an entire keyboard to see text). High effort; irrelevant for thesis writing.

## 2. Academic writing surfaces

**Overleaf.** The key 2024–26 shift: **Writefull is natively integrated into Overleaf** (Digital Science owns both), and Overleaf ships a first-party AI stack: AI Assist (chat), Error Assist (compile-error fixes), language suggestions, rewrite tools, TeXGPT, equation/table generators — plan-gated. Privacy note in Overleaf's own docs: some features send content to third parties **including OpenAI** ("never used to train models"). Before native integration, Writefull for Overleaf was a **browser extension overlaying the CodeMirror editor** — proving the extension route works; **Paperpal and Trinka still ship exactly that** (Chrome extensions checking LaTeX in place). A third party can still reach Overleaf via extension, but competes with a bundled incumbent.

**Word track changes.** The strongest academic-native pattern: Writefull and Paperpal both deliver suggestions in a sidebar and can apply edits; writing edits **as tracked changes** matches how supervisors/co-authors already review — free provenance, undo, and trust.

**Google Docs.** Suggestion mode is culturally ideal but unreachable via public API (see above) — extension overlay or comment-based feedback only.

**Quarto/RMarkdown/VS Code.** This is where LSP tooling already lives: LTeX/LTeX+ (LanguageTool via LSP with genuine LaTeX/Markdown parsers), Harper LSP, Vale, cSpell. Technically-inclined academics *already assemble* this stack (documented in "VS Code for prose" guides and the Awesome Scientific Writing list); Quarto's VS Code visual editor makes prose-in-VS-Code mainstream for R users. **A Quarto-aware checker (chunks, `@key` citations, cross-refs) is an underserved niche** — LTeX+ handles LaTeX/Markdown but not Quarto-specific syntax perfectly, and requires Java/LanguageTool locally.

**Zotero adjacency.** Nothing significant ties grammar tools into Zotero; the relevant adjacency is **citation-key awareness** (don't flag `@turner2020` or `\citep{}` — LTeX+ solves this with configurable ignore-lists; naive checkers fail here, and this is a top academic false-positive source).

**Least-friction surfaces for a PhD student/epidemiologist:** (1) Overleaf — natively occupied by Writefull/AI Assist; third-party entry = extension. (2) Word add-in with tracked changes — supported APIs, matches supervisor workflows. (3) VS Code/Quarto via LSP — smallest audience but cheapest to build, zero platform gatekeeping, and it matches this builder's own workflow.

## 3. LSP as a universal adapter for prose

The LSP model maps cleanly onto writing feedback: **diagnostics** = underlined issues with severity + message; **code actions** = quick-fix replacements; custom commands = add-to-dictionary / disable-rule. Existing prose LSPs: **LTeX+/ltex-ls-plus** (LanguageTool, real LaTeX/Markdown parsing; Java-heavy, slow on large theses per its own FAQ), **Harper** (Rust, on-device, ms latency), **Vale** (style rules via YAML).

**Pros of LSP-first:** one adapter → VS Code, Neovim, Positron, Zed, Helix, Emacs; local processing by default (the privacy story is free); per-project config files checked into the repo (rule tuning that travels with the manuscript); no DOM-overlay engineering. **Cons:** reaches only editor-savvy users; no Overleaf/Word/Docs reach; prose diagnostics can spam — Helix/Neovim users routinely complain about LTeX noise, so rule-tuning UX matters even here.

## 4. Interaction patterns

- **Inline underline + hover card** (Grammarly, LTeX): lowest-friction for *mechanical* errors; the accepted idiom. Risk: visual noise while drafting.
- **Sidebar list** (Grammarly editor, Paperpal, Writefull): better for systematically working through issues at revision time; keeps text clean; supports sorting by category/severity.
- **Margin comments / suggestion-mode edits** (Docs culture, Word track changes): best perceived as "a colleague's feedback"; ideal for higher-level suggestions; provenance and accept/reject built in.
- **On-demand full-document review** (Paperpal manuscript check, Word "Coaching with Copilot"): matches academic revision behavior — writers explicitly report wanting checking *at revision, not while drafting*; multiple sources advise disabling live checking during first drafts to protect flow.
- **Diff views for rewrites:** for sentence-level LLM rewrites, side-by-side or tracked-change-style diffs are the trust mechanism.
- **Accept/dismiss/mute:** the standard triple is accept, dismiss-instance, and **disable-rule/add-to-dictionary**. The FSE 2025 suppression study and static-analysis literature show suppressions accumulate and silently rot — surfacing "what you've muted" matters.
- **Explanation depth:** Grammarly's pattern is one-line reason + expandable "learn more." The Harper HN thread shows users value *auditable* rules ("I can read and change the rule") — explainability is a differentiator vs LLM black boxes, and LLM-checker inconsistency (comma advice "reversing hourly") actively erodes trust.
- **HCI findings on control/ownership:** "Co-Writing with AI, on Human Terms" (PACM HCI 2025) finds desired AI intervention **varies by writing stage**: academics want ownership of planning/ideas and welcome **critical feedback** more than co-generation; recommends customizable control levels mapped to cognitive stages. "Interaction-Required Suggestions" (arXiv 2504.08726) argues for designs requiring engagement rather than frictionless one-click acceptance — preserving felt ownership (directly relevant to journals' authorship anxieties). The Copilot literature ("When to Show a Suggestion?", arXiv 2306.04930) formalizes *when not to show* a suggestion as a learnable decision — over-suggesting reduces net value.
- **False-positive fatigue:** the static-analysis literature (UMD FP-over-time; IEEE TSE 2023 survey) is unambiguous — high FP rates cause tool abandonment and blanket muting; the Harper HN thread shows the same dynamic in prose.

## 5. Latency, architecture, privacy

- **Local-first:** Harper's whole pitch — Rust core, on-device, ms latency, compiles to WASM (its Chrome extension and Obsidian plugin run the same core). LanguageTool is self-hostable (Docker). Emerging pattern: **rule-based tier local + optional LLM tier cloud**.
- **Incremental checking:** debounce keystrokes (~500ms–1s), re-check only the edited paragraph, cache diagnostics keyed by paragraph hash. LTeX is criticized precisely when it fails to do this on large files.
- **Privacy for unpublished manuscripts is a live, documented concern:** Trinka, Enago, eContentPro, CipherWrite all published 2025–26 pieces on whether AI tools "steal" unpublished research; **Elsevier's and Wiley's GenAI policies restrict uploading manuscripts to tools without confidentiality guarantees** (Elsevier's reviewer policy forbids uploading manuscripts to public AI tools outright). Vendors respond with no-training commitments, SOC 2, data residency, opt-outs, and — most credibly — **on-device processing** (Harper). For Researchly's audience this is a primary purchase criterion: local-first rule tier + explicit "nothing leaves your machine unless you invoke the LLM action" is a defensible wedge.

## 6. What indie/OSS builders have learned

- **Harper (Automattic):** rule-based + fast + private wins a real segment, but users compare against Grammarly's recall and punish both gaps and FPs; positioning honesty matters. Auditability of rules is a loved feature.
- **LanguageTool threads:** OSS-core + hosted-premium is sustainable, but the OSS/premium quality gap breeds distrust; self-hosters exist and blog about it.
- **Grammarly's engineering retrospective:** the biggest technical lesson in the space — *don't touch the host DOM*; overlay + rect math + aggressive performance discipline.
- **interface0 (Bromberg):** platform API gaps (Docs suggestions) force fragile automation; pick surfaces with real APIs (Word, LSP).
- **UX consensus across CHI work + reviews:** writers reject tools that (a) interrupt drafting, (b) homogenize voice via over-suggesting rewrites, (c) can't explain themselves, (d) can't be tuned per-document/genre. **Stage-aware assistance (quiet while drafting, thorough at revision) is repeatedly recommended and almost no shipping tool does it explicitly.**

---

## Implications for Researchly

**Recommended integration strategy, ranked by effort→reach for the LaTeX/Overleaf + Word + Quarto academic:**

1. **Core engine as a library + LSP server first.** Lowest effort, zero gatekeepers, dogfoodable in the builder's own Quarto/VS Code workflow; LaTeX/Markdown/Quarto-aware parsing (ignore `\citep`, `@keys`, chunks, math) is the table-stakes differentiator LTeX proved and Quarto under-serves. Diagnostics + code actions + project config = the whole accept/dismiss/mute model for free.
2. **Browser extension for Overleaf (targeted, not universal).** One site, known CodeMirror 6 editor — avoids the general overlay problem; Paperpal/Trinka prove the route; pre-integration Writefull proves adoption. Overlay-not-DOM-mutation. Compete on explainability + privacy + price.
3. **Word add-in (Office JS), writing suggestions as tracked changes.** Moderate effort, high trust-fit with thesis/supervisor workflows; the tracked-changes API is the killer affordance.
4. **Skip/deprioritize:** Google Docs (no suggestion API; universal extension overlay is a Grammarly-scale engineering tax), desktop overlay apps, mobile keyboards.

**Interaction-design principles (evidence-linked):**

- **Stage-aware by default:** a quiet "draft mode" (spell-level only) vs an on-demand "revision review" (full-document pass, sidebar/report) — matches documented academic preferences and interruption-cost complaints.
- **Precision over recall; show fewer, better suggestions** (Copilot "when to show" result; FP-fatigue literature). Track dismissals per rule and auto-attenuate.
- **Every suggestion explainable:** one-line reason + expandable rationale; auditable/open rules as a trust feature.
- **Native provenance affordances:** tracked changes in Word, diffs for any rewrite; never silently apply.
- **Mute is first-class:** rule-level, term-level (dictionary), project-level config that lives with the manuscript; plus a visible "muted rules" review.
- **Protect voice:** default to flagging + minimal edits, not paraphrase; put rewrite tools behind explicit invocation (ownership findings; journal authorship policies).
- **Privacy as architecture:** local rule tier always; cloud/LLM tier opt-in per action, with no-training + security posture stated in-product.

---

## Sources

- Grammarly engineering: https://www.grammarly.com/blog/engineering/making-grammarly-feel-native-on-every-website/
- SDK shutdown: https://techcrunch.com/2023/07/13/grammarly-to-shut-down-the-text-editor-sdk-in-january/ ; https://sapling.ai/docs/sdk/Integration%20Details/grammarly-migration/ ; https://blog.wproofreader.com/migrating-from-grammarly-sdk-to-an-alternative-solution/ ; https://github.com/MarkEdit-app/MarkEdit/issues/387
- Overleaf/Writefull: https://docs.overleaf.com/integrations-and-add-ons/ai-features ; https://www.overleaf.com/blog/update-writefull-is-now-integrated-with-overleaf-no-extension-needed ; https://help.writefull.com/writefull-for-overleaf--user-guide ; https://blog.writefull.com/texgpt-harness-the-power-of-chatgpt-in-overleaf/ ; https://www.digital-science.com/press-releases/digital-science-launches-new-cutting-edge-ai-writing-tools-for-20-million-overleaf-users/
- Paperpal/Trinka: https://paperpal.com/paperpal-for-overleaf ; https://paperpal.com/paperpal-ms-word-add-in ; https://support.paperpal.com/support/solutions/articles/3000125409 ; https://www.trinka.ai/
- Word tracked changes API: https://learn.microsoft.com/en-us/javascript/api/word/word.trackedchangecollection?view=word-js-preview ; https://learn.microsoft.com/en-us/javascript/api/word/word.changetrackingmode?view=word-js-preview
- Google Docs API gap: https://developers.google.com/workspace/docs/api/how-tos/suggestions ; https://issuetracker.google.com/issues/287903901 ; https://andybromberg.com/interface0-google-docs
- LSP tools: https://github.com/ltex-plus/ltex-ls-plus ; https://ltex-plus.github.io/ltex-plus/faq.html ; https://writewithharper.com/ ; https://news.ycombinator.com/item?id=44331362 ; https://dev.to/meilisearch/prose-linting-with-vale-5hj3 ; https://stebalien.com/blog/grammar-tools-in-emacs/
- Academic VS Code/Quarto: https://danmackinlay.name/notebook/vs_code_for_prose.html ; https://quarto.org/docs/tools/vscode/visual-editor.html ; https://writing-resources.github.io/awesome-scientific-writing/
- HCI research: https://arxiv.org/abs/2504.12488v1 ; https://dl.acm.org/doi/10.1145/3757566 ; https://arxiv.org/html/2504.08726v1 ; https://arxiv.org/html/2306.04930v3 ; https://dl.acm.org/doi/10.1145/3613904.3642625
- FP fatigue: https://www.cs.umd.edu/~pugh/BugWorkshop05/papers/34-chou.pdf ; https://dl.acm.org/doi/10.1109/TSE.2023.3329667 ; https://software-lab.org/publications/fse2025_suppressions.pdf
- Desktop/mobile: https://support.grammarly.com/hc/en-us/articles/4406998780813 ; https://developer.apple.com/forums/thread/720686 ; https://www.grammarly.com/blog/engineering/how-grammarly-built-a-native-keyboard-for-android/
- Privacy/publisher policies: https://www.trinka.ai/blog/is-it-safe-to-use-ai-tools-for-unpublished-research-manuscripts/ ; https://www.elsevier.com/about/policies-and-standards/generative-ai-policies-for-journals ; https://www.wiley.com/en-us/publish/article/ai-guidelines/ ; https://www.econtentpro.com/blog/are-you-giving-away-your-research-when-you-use-ai-tools/431 ; https://cipherwrite.com/blog/are-ai-writing-tools-stealing-your-work-2026
- Self-hosting/indie: https://wiki.ethanppl.com/blog/2026/05/11/self-host-language-tools ; https://www.codeslikeaduck.com/posts/selfhostlanguagetool/ ; https://github.com/riponcm/GemType ; https://concurate.com/grammarly-review/
