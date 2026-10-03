# Landscape Research 02 — Open-Source Grammar/Style/Prose Engines

*Researchly project · Landscape research phase · Compiled 2026-08-10.*
*Focus: what exists, how rules/checks are expressed, licenses, and what Researchly could build on or borrow. Sources at the end.*

---

## 1. LanguageTool

- **License:** LGPL-2.1+ (core). Open-core model: the rule engine, ~30+ languages of rules, and the HTTP server are open source; Premium adds extra rules, AI rephrasing, and remote-only ML checks that never ship in the OSS repo.
- **Language/architecture:** Java (~91%), Maven multi-module build (core, server, CLI, GUI, office extensions). ~14.6k stars, ~82k commits, actively developed; requires Java 17; full clone >500 MB. Checks run via `JLanguageTool` over analyzed (tokenized, POS-tagged) sentences.
- **Rule model — three tiers:** (1) **XML pattern rules** — token/regex/POS patterns with messages, suggestions, and examples; authorable by non-programmers via a web rule editor; (2) **Java rules** for anything needing logic; (3) optional **n-gram data** (~8 GB Google n-grams) for confusion-pair detection ("their/there"), plus server-side (non-OSS) neural checks.
- **Deployment/API:** well-documented self-hostable HTTP server (`/v2/check`), community Docker images, public API with rate limits. 2026 blog posts (e.g., Ethan Lee's self-hosting writeup) show self-hosting is a common response to Premium paywalling.
- **Academic English quality:** strong on mechanics, agreement, typography, confusables; has a "picky mode" and style categories, but no notion of scientific register, section conventions, or hedging norms. False-positive management (per-rule disable, dictionaries) is mature.
- **Verdict:** best-in-class *breadth* engine callable today. Heavy (JVM, RAM) and awkward to embed in a lightweight local tool, but excellent as an optional backend service. The **XML declarative rule structure (pattern + typed category + message/short-message/examples) is directly stealable** for Researchly's typed-suggestion design.

## 2. Harper (Automattic)

- **License/stack:** Apache-2.0, Rust core (compiles to WebAssembly), ~10.5–13k stars, v2.1.0 (Apr 2026), very active; adopted by Automattic and marketed explicitly as the privacy-first Grammarly/LanguageTool alternative ("LanguageTool needs gigabytes of RAM; Harper runs in milliseconds locally").
- **Architecture:** `harper-core` (tokenizer, POS-ish tagging, linter framework) + format-aware front-ends (`harper-html`, **`harper-tex`**, `harper-asciidoc`, `harper-python` for comments/docstrings) + `harper-ls` (LSP server on crates.io and npm) + `harper.js` (WASM) + Chrome extension, Obsidian plugin, VS Code/Neovim/Helix/Emacs/Zed integrations.
- **Rules/extensibility:** built-in rules are Rust "linters"; the big 2025–2026 development is **Weir**, a small DSL for custom rules: expressions over tokens with sequences `()`, alternatives `[]`, filters `<>`, UPOS tags, wildcards, exceptions; each rule carries `message`, `description`, `becomes` (suggested fix) and inline `test`/`allows` cases; rules bundle as **Weirpacks** (zip + manifest) loaded via `--weirpack`; there's an in-browser Weir studio, and the author has written about LLM-generated Weir rules and a future Weir marketplace.
- **Limits:** English only; grammar coverage narrower/shallower than LanguageTool (no n-gram/ML confusion detection); tone/style feedback minimal.
- **Verdict:** the strongest **architectural match** for Researchly: local-first, fast, LaTeX-aware tokenization, LSP + WASM delivery, and a rule DSL with built-in suggested-fix + tests (almost exactly the "explainable typed suggestion" object Researchly wants). Realistic options: build on harper-core and ship scientific-style rules as a Weirpack, or copy its architecture (core engine → LSP → WASM → extensions).

## 3. Vale

- **License/stack:** MIT, Go; now under the `vale-cli` org (formerly errata-ai); the de facto standard prose linter for docs teams (Datadog, Spectro Cloud, GitLab publish their Vale workflows).
- **Rule model:** styles are directories of **YAML rules**, each an instance of a check type: `existence`, `substitution`, `occurrence`, `repetition`, `consistency`, `capitalization`, `conditional`, `metric` (readability formulas), `spelling`, `sequence` (NLP token sequences), and `script` (Tengo scripting for arbitrary logic). Each rule has a message, severity (suggestion/warning/error), and link — a clean, human-authorable severity/typing scheme.
- **Ecosystem:** `vale-cli/packages` distributes ready-made styles — Microsoft, Google, write-good, proselint, alex, Joblint reimplemented as Vale styles — installable via `vale sync`. `vale-ls` provides an LSP server; `vale-native` supports browser-extension use.
- **Markup-awareness:** parses Markdown, AsciiDoc, reStructuredText, HTML, XML, DITA, org; skips code blocks intelligently. **No native LaTeX support** — a real gap for Researchly's audience.
- **Verdict:** the best existing vehicle for *codifying a scientific style guide* (terminology, forbidden hedges, unit formatting, "utilize→use", per-section passive-voice metrics via per-path configs). But it is terminology/pattern linting, not grammar. Steal: the YAML check-type taxonomy, the severity model, and package/`sync` distribution of styles.

## 4. Smaller prose linters

- **textlint** — MIT, TypeScript, 3.1k stars, very actively maintained (v15.7.1, May 2026). Pluggable, **AST-based** (parses Markdown/plain text into a TxtNode AST; HTML/reST/AsciiDoc via plugins); zero built-in rules — 100+ rules ship as npm packages; four extension points (rules, filter rules, presets, plugins). Used by Vue, Cypress, webpack docs. *Verdict:* excellent **plugin-architecture pattern** (rule-as-package, AST visitors, filter rules for suppressions); the JS ecosystem may not fit a Rust/Python build, but the design is worth copying.
- **proselint** — BSD-3-Clause, Python, 4.5k stars; ~70 checks encoding usage authorities (Garner, Orwell); revived after dormancy: v0.16.0 (Nov 2025). Checks are simple Python functions (mostly regex existence checks). *Verdict:* pleasant Python rule idiom and a source of checks to port; too shallow to be an engine.
- **write-good** — MIT, JavaScript; naive checks (passive voice, weasel words, lexical illusions, clichés). Effectively **dormant**; lives on mainly as a Vale style. *Verdict:* mine the check list; don't build on it.
- **alex** — MIT, JavaScript, built on the retext/nlcst NLP AST; catches insensitive language. Low activity; also a Vale style. *Verdict:* niche; the retext plugin pipeline is a minor architectural reference.
- **RedPen** — Apache-2.0, Java; validator for technical documents, XML config, extensible with Java/JavaScript validators; notably parses **LaTeX**, Markdown, AsciiDoc, reST. Last release Jan 2020 — unmaintained. *Verdict:* avoid as a dependency; its section-aware document model + LaTeX parsing is a useful design precedent.

## 5. LTeX / ltex-ls / ltex-ls-plus

- **Status:** original `valentjn/ltex-ls` is abandoned; the community fork **`ltex-plus/ltex-ls-plus`** (MPL-2.0, latest 18.6.1, Oct 2025, active) is the continuation.
- **What it does:** wraps a bundled LanguageTool in an **LSP server**. Parses **LaTeX, BibTeX, ConTeXt, Markdown, MDX, Typst, AsciiDoc, Org, Quarto, R Markdown/Sweave, reST, XHTML, git commits, and code comments**, building an *annotated text* mapping: markup is stripped or replaced ("dummy" words for `\ref{}`, math becomes a placeholder noun) while preserving original source offsets, so diagnostics land on the right LaTeX characters. Configurable per-command/per-environment handling, user dictionaries, "hidden false positives," per-rule disabling, multilingual support, and offloading to an external LanguageTool server.
- **Verdict:** *the* proven integration pattern for Researchly: **markup → plain-text projection with offset mapping → checker → diagnostics mapped back → LSP quick-fixes**. Its weaknesses (JVM weight, single-checker coupling) define exactly what Researchly could improve: a lightweight server that fans out to multiple checkers (rules + ML) behind one LSP.

## 6. ML / GEC components

- **GECToR** (Grammarly, Apache-2.0): "tag, not rewrite" — a transformer encoder tags each token with edit operations, ~10x faster-than-seq2seq inference and, crucially, **span-level, explainable edits**. Official repo essentially frozen (research code, AllenNLP-era); `gotutiyan/gector` is a maintained unofficial PyTorch reimplementation with pretrained weights. *Verdict:* the edit-tagging paradigm is ideal for Researchly's typed-suggestion UI; expect to retrain/modernize rather than run the 2020 code as-is.
- **T5-based GEC / instruction editors:** `vennify/t5-base-grammar-correction` (CC-BY-NC-SA, JFLEG-trained), `pszemraj/flan-t5-large-grammar-synthesis`, and **Grammarly CoEdIT** (`grammarly/coedit-large` = Flan-T5-large 770M, up to 11B) — instruction-tuned for GEC, clarity, formality, paraphrase, simplification — very close to Researchly's Improvement category — **but CC-BY-NC-4.0 (non-commercial)**, with the CoEdIT dataset on HF for retraining. Many popular GEC checkpoints carry NC licenses — **license audit is mandatory** before productizing.
- **ERRANT** (`chrisjbryant/errant`, MIT, v3.0.2 May 2026, maintained): aligns original/corrected sentence pairs, extracts edits, and classifies them into ~25 rule-derived error types (via spaCy POS/lemma/dependency); outputs M2; `errant_compare` gives P/R/F0.5 per error type. English-only. *Verdict:* dual use — (a) evaluation harness for any GEC component, (b) **auto-typing raw LLM rewrites into labeled edits** (diff a model's rewrite against the source, classify each edit, present as typed suggestions).
- **Academic-writing-specific models:** no widely adopted open GEC model fine-tuned specifically for academic prose exists; adjacent work is research-stage (OpenReviewer, arXiv work on reward models for scientific-writing evaluation, university fine-tuning projects). **A genuine open niche** — Researchly could fine-tune a small model (CoEdIT-style, on a permissively licensed base + arXiv-derived edit data) and be first.
- **Local LLM wrappers:** `theJayTea/WritingTools` (system-wide hotkey assistant; works with Ollama/local LLMs), `swadhinbiswas/opengrammar`, plus many small Ollama proofreading scripts. These validate the "local LLM as clarity engine" pattern but are UX shells — none produce structured, span-anchored, typed suggestions.

## 7. Editor-integration plumbing

- **LSP is the winning delivery mechanism:** three independent ecosystems converged on it — `harper-ls`, `vale-ls`, `ltex-ls-plus` — giving one server → VS Code/Neovim/Emacs/Helix/Zed "for free"; diagnostics = suggestions, code actions = fixes/"add to dictionary"/"ignore rule". Overleaf/Word/browser need separate shims (WASM in-browser like Harper's extension; Office JS add-in; or clipboard/hotkey like WritingTools).
- **Glue projects:** `jeertmans/languagetool-rust` (Rust client + CLI for the LT HTTP API), `caderek/gramma` (Node CLI on LT API), `vigoux/languagetool.nvim`, various per-language LT clients. All confirm the pattern: keep the checker behind an HTTP/LSP boundary.

---

## Implications for Researchly

**Candidate build-on strategies:**

1. **Harper-core + Weirpacks (closest fit):** Rust, Apache-2.0, local-first, LaTeX/Markdown tokenizers, LSP + WASM already built. Write scientific conventions as Weir rules; contribute upstream where general. Risk: grammar depth below LanguageTool; Weir is young; Automattic controls direction.
2. **Orchestrator pattern (recommended architecture):** a lightweight LSP server (Rust or Python) that does ltex-style markup→text projection with offset maps, then fans out to pluggable engines: Harper or LanguageTool (self-hosted, LGPL-safe over HTTP) for grammar; Vale-style YAML rules for scientific terminology/conventions; optional local LLM (Ollama) whose rewrites are diffed and **typed via ERRANT** into Correction/Improvement suggestions. This directly yields the four-way suggestion typology.
3. **Vale-first MVP:** ship a "Researchly scientific style" as a Vale package + vale-ls for immediate adoption by docs-literate users; limited by no LaTeX support and no real grammar.

**Comparison sketch:**

| Engine | Depth | Weight | LaTeX | Custom rules | License risk |
|---|---|---|---|---|---|
| LanguageTool | high (grammar) | heavy (JVM, GBs) | via LTeX+ | XML (good) | LGPL, open-core creep |
| Harper | medium, improving | very light | native | Weir DSL | Apache-2.0, none |
| Vale | style only | light | **no** | YAML (best UX) | MIT, none |
| textlint | medium (style) | light (Node) | no | JS packages | MIT, none |
| GEC models | high (fluency) | GPU-ish | n/a | fine-tune | **many NC licenses** |

**Patterns to steal regardless of engine:** ltex-ls-plus's annotated-text offset mapping; Vale's check-type taxonomy + severity levels + `sync` package distribution; Harper's rule DSL with embedded tests and `becomes` fixes; LanguageTool's rule metadata (message/short message/examples/category); ERRANT's edit typology for explainability; textlint's filter-rule suppression model.

**Avoid:** RedPen (dead), write-good/alex as engines (shallow/dormant), original ltex-ls (use the plus fork), NC-licensed GEC checkpoints in anything distributable.

---

## Sources

- LanguageTool: https://github.com/languagetool-org/languagetool ; https://languagetool.org/dev ; https://wiki.ethanppl.com/blog/2026/05/11/self-host-language-tools
- Harper: https://github.com/Automattic/harper ; https://writewithharper.com/docs/weir ; https://writewithharper.com/docs/integrations/language-server ; https://elijahpotter.dev/articles/building-the-weir-language ; https://elijahpotter.dev/articles/generating-weir-code-with-LLMs
- Vale: https://vale.sh/ ; https://docs.vale.sh/ ; https://github.com/vale-cli/vale ; https://github.com/vale-cli/packages ; https://github.com/vale-cli/vale-ls ; https://www.datadoghq.com/blog/engineering/how-we-use-vale-to-improve-our-documentation-editing-process/ ; https://www.spectrocloud.com/blog/how-we-use-vale-to-enforce-better-writing-in-docs-and-beyond
- Small linters: https://github.com/textlint/textlint ; https://github.com/amperser/proselint ; https://github.com/redpen-cc/redpen ; https://earthly.dev/blog/markdown-lint/
- LTeX+: https://github.com/ltex-plus/ltex-ls-plus ; https://ltex-plus.github.io/ltex-plus/ ; https://github.com/valentjn/ltex-ls
- ML/GEC: https://github.com/grammarly/gector ; https://arxiv.org/abs/2005.12592 ; https://github.com/gotutiyan/gector ; https://github.com/chrisjbryant/errant ; https://huggingface.co/grammarly/coedit-large ; https://huggingface.co/datasets/grammarly/coedit ; https://arxiv.org/html/2412.11948v3 ; https://arxiv.org/html/2601.11374v1 ; https://warwick.ac.uk/fac/cross_fac/eduport/edufund/projects/yang/projects/fine-tuning-language-models-for-scientific-writing-support/
- Plumbing/alternatives: https://github.com/jeertmans/languagetool-rust ; https://github.com/caderek/gramma ; https://github.com/theJayTea/WritingTools ; https://github.com/swadhinbiswas/opengrammar ; https://www.localalternative.io/alternatives/grammarly
