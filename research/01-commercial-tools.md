# Landscape Research 01 — Commercial Writing Assistants

*Researchly project · Landscape research phase · Compiled 2026-08-10.*
*Prices and features change frequently; items marked "reported" come from third-party reviews and may lag the products. Sources at the end.*

---

## 1. Grammarly (now under parent company "Superhuman")

**Positioning & corporate context.** Grammarly is the category-defining general-purpose writing assistant (~40M daily users claimed). In late 2024–2025 it acquired Coda and Superhuman (email), and in **October 2025 the parent company rebranded to "Superhuman"**, launching "Superhuman Go," an agentic AI assistant that works across apps; the Grammarly writing product retains its name inside the suite. Strategic direction is now "AI productivity suite with agents," not just writing correction.

**Interaction model.**

- **Inline underlines** in almost any text field (browser extension, desktop app, Word/Docs add-ins, mobile keyboard). Red = correctness; blue = clarity; green = engagement; purple = delivery/tone; gray = enterprise style-guide rules.
- **Hover/click cards**: clicking an underline opens a compact card showing the proposed replacement, a one-line rationale, and buttons to accept, dismiss, or (for some types) a longer "Learn more" explanation of the grammar rule. One-click accept applies the edit in place.
- **Sidebar editor view**: the Grammarly Editor lists all suggestions grouped by the four categories, with an overall document score and per-category tallies.
- **Goals/audience settings**: users set audience (general → expert), formality, domain (academic, business, email, casual, creative), and intent; suggestions and the score recalibrate. "Academic" domain tightens formality and flags contractions, informal terms, etc.
- **Tone detector**: passively estimates how the text "sounds" (confident, friendly, formal…) via emoji/labels; tone *rewrite* suggestions are Premium.
- **Acceptance flow**: everything is opt-in per suggestion; users can dismiss individual suggestions, turn off whole categories, or add words to a personal dictionary.
- **Generative AI**: prompt-based compose/rewrite/reply ("improve it," "make it persuasive," shorten, ideate), integrated via a sparkle icon; strategic suggestions and agent actions in the 2025+ suite.

**Architecture (public knowledge).** Grammarly Research published **GECToR** ("Grammatical Error Correction: Tag, Not Rewrite," BEA 2020): GEC framed as *sequence tagging* with pretrained transformer encoders (RoBERTa/XLNet), predicting token-level edit tags (keep/delete/append/replace plus g-transformations like case changes and verb-form changes), applied **iteratively**, achieving then-SOTA F0.5 while being up to ~10x faster at inference than seq2seq — which is what made real-time inline checking economical. Follow-up work covered ensembling/knowledge distillation for sequence taggers. The modern product layers LLM-based rewriting/generation on top of this classic tagging stack (the exact current mix is not public).

**Pricing (reported 2026).** Free tier (correctness + basic clarity); Pro/Premium ≈ $12/mo annual, $30/mo monthly; Business/Enterprise per-seat with style guides, brand tones, analytics.

**Strengths.** Ubiquity (works where you write); frictionless accept/dismiss loop; clear color-coded taxonomy; brief explanations that teach; low-latency inline checks; mature dismiss/ignore controls.

**Reported weaknesses for academic/scientific writing.** Peer-reviewed evaluations (e.g., Heliyon 2024, "Exploring the use of Grammarly in assessing English academic writing") and reviewer consensus report: **over-flagging of passive voice** (standard in methods sections); a push toward generic "plain business English" that strips discipline conventions and calibrated hedging; flags technical terminology and Latin abbreviations; no awareness of IMRaD section conventions, statistical wording, or citation-claim alignment; it "can make a weak argument sound smoother — not stronger." Its four categories do not distinguish "violates a rule" from "violates a convention of your genre."

---

## 2. Academic-focused tools

### 2.1 Writefull (Digital Science; sibling of Overleaf)

- **Target user:** researchers, PhD students, ESL/STEM authors, LaTeX users.
- **Capabilities:** language check using a model **trained on published research texts and tailored to LaTeX** (skips markup, doesn't flag technical terms); optional GPT model with custom prompts. Widgets: Paraphraser (3 intervention levels), Academizer (informal → formal), Change Style (scientific/concise/punchy), Title & Abstract Generator, **TeXGPT** (generate LaTeX for tables/equations/figures), Split/Join sentences, Synonyms in Context.
- **Distinctive corpus features:** **Language Search** (query how real published papers phrase something, with frequency evidence) and **Sentence Palette** (curated section-specific phrase bank: Introduction/Methods/Results/Discussion). These treat the literature as ground truth for convention — a genuinely different paradigm from rule-based correction.
- **Integration:** natively built into **Overleaf** (no extension), Word add-in, web app ("Writefull X"). No Google Docs, no mobile.
- **Interaction:** underlines → click → card; per-suggestion accept/reject plus sentence-level accept-all/reject-all.
- **Pricing (reported):** free tier with daily quotas; Premium ≈ $21/mo or ~$150/yr; institutional licenses (1,500+ universities); Revise/Cite features institution-only.
- **Doesn't do:** deep tone/hedging analysis, statistical-reporting checks, explanation of *why* an edit is suggested (edits are largely unexplained diffs).
- **Reported weaknesses:** over-formalizes; suggestion rationale is thin; weaker overall grammar coverage than Grammarly on general text.

### 2.2 Paperpal (Cactus Communications / Editage)

- **Target user:** researchers preparing journal submissions, heavily ESL market; trained on Editage's professionally edited manuscript corpus (17+ years of editing data, per marketing).
- **Capabilities:** academic-register language suggestions with **Essential vs Extensive edit modes** (a depth dial); consistency checks (spelling variants, hyphenation); paraphrase/trim; academic translation (30+ languages); templates (outlines, abstracts); **30+ pre-submission "submission readiness" checks** (technical compliance, ethics declarations, references); plagiarism; "Research | Cite" literature search over 250M+ papers with citation generation (10,000+ styles); PDF chat.
- **Integration:** web editor, MS Word add-in, browser extension for Docs/web; Overleaf integration announced/forthcoming (verify status).
- **Interaction:** sidebar list of suggestions with accept/reject per item; tracked-changes-style output in Word.
- **Pricing (reported):** free ≈ 200 suggestions/mo; Prime ≈ $25/mo, ~$139/yr.
- **Doesn't do:** statistical/causal wording checks; explanation pedagogy is limited.

### 2.3 Trinka (Crimson AI / Enago)

- **Target user:** academic and technical writers, especially medical/life sciences.
- **Capabilities:** grammar in **"Lite" vs "Power" modes**; academic tone and formal-register suggestions; discipline-aware corrections; **style-guide modes (APA, IEEE, ACS, AGU)**; consistency checks; **unbiased/inclusive language** checks; technical word-choice suggestions. Distinctive **Publication Readiness Checks** (25+ automated checks): journal scope match, technical compliance (length, headings), **ethical compliance** (consent, ethics approval, COI), authorship details, **retracted/obsolete reference alerts**, figure/table captions, **clinical trial ID verification**, keywords/summary. Marketing has also referenced statistics-reporting guidance (e.g., P-value formatting conventions) — coverage depth uncertain.
- **Integration:** web editor, Word add-in, browser extension, **offline desktop app** (top tier, for confidential data — notable for clinical users; SOC2/HIPAA/ISO/GDPR claims).
- **Pricing:** free 5,000 words/mo; Premium / Premium Plus (roughly $7–$14/mo reported); credits system for reports.
- **Weaknesses:** UI less polished; suggestion latency; general-English coverage below Grammarly.

### 2.4 Curie (AJE / American Journal Experts, now MPS Limited)

- **Target user:** researchers wanting "professional editing quality" automated; leverages AJE's human-editing heritage; used by 3,000+ labs/institutions incl. publisher partnerships.
- **Capabilities:** manuscript editing delivered **as tracked changes**; clarity/precision suggestions preserving scientific terminology; **academic translation** (Chinese/Portuguese/Spanish → English; Premium: 2/mo); explicitly "a writing assistant, not a paper generator."
- **Integration:** web workspace + MS Word add-in.
- **Pricing:** 7-day trial; Premium ≈ $11.25/mo annual ($16 monthly); group/enterprise tiers.
- **Doesn't do:** inline real-time checking across surfaces; research/citation features; explanations per edit.

### 2.5 InstaText

- **Target user:** researchers/academics, especially non-native speakers, wanting whole-sentence rewriting rather than error flags.
- **Capabilities:** rewrites text for clarity/readability/flow in one pass ("one refined version, no prompt engineering"); explicitly **"improves without generating new content"** (authorship-preservation framing); personal dictionary for terminology; UK/US dialect and formality settings.
- **Interaction:** paste or type → click Improve → **diff view with per-change accept/reject**; exports to Word as Track Changes. Editor-like rather than checker-like.
- **Integration:** web editor, browser extension, Word add-in (Track Changes), works over Google Docs and Overleaf via extension.
- **Pricing (reported):** ≈ $29/mo, cheaper annually.
- **Weaknesses:** no explanations at all; can rewrite more aggressively than users want; no section/discipline awareness.

---

## 3. LLM-era tools

### 3.1 Jenni AI
Document editor for students/researchers built around **AI autocomplete** (continues from your last sentence), in-text citations from an uploaded library (2,600+ styles), chat-with-PDF, paraphrase, outlines/IMRaD structure. Free tier (limited daily words) / ~$12–20/mo unlimited. Reported weaknesses: shallow academic depth, **citation fabrication risk**, and complaints of "silent, unauthorized changes" to text — a cautionary interaction-design tale. (Some criticism sourced from a competitor's review; treat as directional.)

### 3.2 SciSpace
Research workspace (280M+ paper index): Copilot chat-with-PDF, literature review matrix, paraphraser, AI detector, and an **AI Writer** that autocompletes, suggests edits, and inserts citations from its index; exports to Word/LaTeX. ≈ $20/mo premium. Writing assistance is generation-first, not correction-first; little transparency about suggestion rationale.

### 3.3 Elicit
Primarily evidence synthesis (screening, data extraction, systematic-review workflows and report generation, added 2024–2025), not a prose assistant. Relevant to Researchly mainly as a signal: researchers increasingly expect writing tools to **connect claims to evidence**, not just polish sentences.

### 3.4 Microsoft Editor / Word Copilot
Editor provides free basic spelling/grammar plus refinements (clarity, conciseness, formality) in Word/Outlook/browser with a per-category "Editor score" pane. Copilot adds draft/rewrite ("Draft with Copilot," rewrite selection, tone change) and **"Coaching with Copilot"**: on-demand, document-level feedback "beyond grammar and spelling" — critique-style comments on clarity, tone, structure that the user applies manually (rolled out 2024–2025, Word web/desktop with an M365 Copilot license). Ubiquity + zero extra cost makes it the default competitor; it has no scientific-genre awareness.

### 3.5 Notion AI
General workspace AI: rewrite/summarize/translate/change-tone commands on selected text, Q&A over workspace, database autofill; 2025 moved toward agentic features and bundled AI in paid plans. Not academic; relevant as a UX reference for **command-palette-on-selection** interaction.

### 3.6 Other notable 2024–2026 entrants

- **Nature Research Assistant (Springer Nature, beta 2025–2026):** reading assistant + **"Manuscript Adviser"** giving actionable feedback on style, structure, substance, missing references, alternative titles/abstracts; explicit no-training-on-your-content stance. A major publisher entering pre-submission feedback — the closest new competitor in spirit to Researchly.
- **Thesify, ProofreaderPro, Manusights** and similar small tools: manuscript-feedback / "reviewer simulation" niches. The ecosystem is fragmenting into (a) polishers, (b) generators, (c) manuscript-level advisers.

---

## 4. Implications for Researchly

### ADOPT (proven patterns to take as-is)

1. **Inline underline → hover card → one-click accept/dismiss** (Grammarly): the industry-standard low-friction loop; keep latency low via a cheap tagging model (GECToR-style) for local edits, reserving LLM calls for rewrites.
2. **Color-coded suggestion taxonomy with per-category toggles** — maps directly onto Researchly's Correction / Improvement / Convention / Preference; no incumbent distinguishes rule vs genre-convention vs taste, so making that distinction explicit in the UI is differentiating *and* familiar.
3. **Short rationale on every card + optional "learn more"** (Grammarly): explanation builds trust and teaches; Writefull/InstaText's unexplained diffs are a known gap.
4. **Corpus-as-evidence features** (Writefull's Language Search / Sentence Palette): justify Convention suggestions with "how published papers in your field phrase this," with frequency evidence — ideal grounding for section-aware conventions.
5. **Tracked-changes / per-change diff review for whole-sentence rewrites** (InstaText, Curie): heavier edits need a diff paradigm, not silent replacement.
6. **Goals panel** (Grammarly): document type (abstract, methods, discussion, grant, response-to-reviewers), audience, journal/style guide — set once, calibrate everything.
7. **Privacy tiers** (Trinka's offline mode; Writefull's zero retention; Nature's no-training pledge): table stakes for unpublished manuscripts and clinical data.

### ADAPT (good ideas needing modification)

1. **Tone detector → hedging/claim-strength meter**: repurpose Grammarly's passive tone read-out into calibrated-confidence feedback ("this Discussion makes 3 causal claims from observational data"; "hedging density unusually high for a Results section").
2. **Submission-readiness checks** (Paperpal 30+, Trinka 25+): valuable but siloed in separate reports/credits; Researchly should surface the writing-relevant subset (retracted refs, missing ethics statement, stats-reporting completeness like CIs with point estimates, CONSORT/STROBE wording) *inline, in context*, not as a gated PDF report.
3. **Edit-depth modes** (Paperpal Essential/Extensive; Trinka Lite/Power; InstaText intervention levels): adapt into a per-category aggressiveness dial (Corrections always on; Preferences off by default).
4. **Coaching-style document-level feedback** (Word Coaching with Copilot, Nature Manuscript Adviser): offer an on-demand "reviewer lens" pass distinct from inline checking — comments, not auto-edits.
5. **Section-aware phrase support** (Writefull Sentence Palette): adapt from a static phrase bank to context-triggered suggestions keyed to the detected section and study design.

### AVOID

1. **Genre-blind rules**: passive-voice and formality nagging calibrated for business English (Grammarly's most-cited academic failure). Every rule needs section- and genre-conditional firing.
2. **Silent or unattributed text changes** (Jenni complaints): never modify text without explicit acceptance; authorship integrity is existential for academics.
3. **Hallucinated citations / generation-first framing** (Jenni, SciSpace risk): position as assistant-not-generator (Curie/InstaText framing) — also the safe posture under journal AI policies.
4. **Score gamification pushing toward uniform prose**: an overall "score" incentivizes accepting everything; if scoring, score per-dimension and make Preference items score-neutral.
5. **Feature sprawl / suite creep** (Grammarly→Superhuman drift): incumbents are diluting focus on writing quality — a focused scientific-writing tool has a clear lane.
6. **Locking core value behind credits/institutional tiers** (Trinka credit reports; Writefull institution-only Cite/Revise): frustrates individual researchers, the likeliest early adopters.
7. **No-explanation edits** (InstaText, Writefull default): explanations are the trust currency for expert users who will push back on suggestions.

**Pricing envelope observed:** academic tools cluster at **$11–25/mo individual** with meaningful free tiers; institutional licensing is the growth channel (Writefull's 1,500 universities); Grammarly anchors the generalist ceiling at ~$12–30/mo.

---

## Sources

- Grammarly interaction & categories: https://support.grammarly.com/hc/en-us/articles/19812297751053-Get-started-with-Grammarly ; https://www.grammarly.com/tone ; https://www.grammarly.com/blog/product/tone-suggestions/ ; https://www.contentgrip.com/grammarly-review-ai-tool/
- GECToR / architecture: https://aclanthology.org/2020.bea-1.16.pdf ; https://www.grammarly.com/blog/engineering/gec-tag-not-rewrite/ ; https://www.grammarly.com/blog/engineering/experimenting-with-gector/ ; https://github.com/grammarly/gector
- Grammarly→Superhuman rebrand: https://www.grammarly.com/blog/company/announcing-company-rebrand-to-superhuman/ ; https://siliconangle.com/2025/10/29/grammarly-transforms-ai-enabled-productivity-suite-superhuman-rebrand/
- Grammarly academic critique: https://manusights.com/blog/is-grammarly-good-for-academic-writing ; https://pmc.ncbi.nlm.nih.gov/articles/PMC11327564/ (Heliyon 2024)
- Writefull: https://help.writefull.com/writefull-for-overleaf--user-guide ; https://www.overleaf.com/blog/update-writefull-is-now-integrated-with-overleaf-no-extension-needed ; https://englishfix.net/reviews/writefull
- Paperpal: https://researcher.life/blog/article/paperpal-review-key-features-pricing-plans-and-how-to-use/ ; https://paperpal.com/pricing
- Trinka: https://www.trinka.ai/pricing ; https://www.trinka.ai/publication-check/
- Curie/AJE: https://r.journalexperts.com/curie ; https://www.mpslimited.com/press/mps-acquires-aje-to-scale-ai-capabilities-and-enter-b2c-market/
- InstaText: https://instatext.io/academic-writing/
- Jenni AI: https://paperpal.com/blog/researcher-resources/jenni-ai-review-and-alternatives (competitor review; directional) ; https://jenni.ai/autocomplete
- SciSpace: https://scispace.com/ai-writer
- Microsoft Editor/Copilot Coaching: https://techcommunity.microsoft.com/blog/microsoft365copilotblog/use-coaching-with-copilot-suggestions-on-how-to-improve-your-content-in-word/4264558 ; https://www.computerworld.com/article/3479705/how-to-use-microsoft-copilot-for-writing-in-microsoft-365-word-outlook-onenote.html
- Notion AI: https://kipwise.com/blog/notion-ai-features-capabilities ; https://fazm.ai/blog/notion-ai-updates-2025-2026
- Nature Research Assistant: https://natureresearchassistant.com/
- Elicit: https://scrollwell.com/guide/tools/elicit-ai-research-tool-review-new-features-2025/
