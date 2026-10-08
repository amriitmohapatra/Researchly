/**
 * The selling point (PLAN.md S4, owner framing 2026-10-08). Static copy,
 * below the checker: people come to check a draft first.
 *
 * Every claim here is a row of ARCHITECTURE.md §1.3; do not add claims
 * that table does not make. Plain English, no superlatives, no numbers.
 */
export function WhyResearchly() {
  return (
    <section className="why" aria-labelledby="why-heading" data-testid="why-researchly">
      <h2 id="why-heading">Why Researchly</h2>
      <p className="why-problem">
        Feedback on scientific writing usually arrives late, after a draft has gone to a supervisor or a reviewer,
        and no two readers give the same advice. The tools that exist either check grammar or write the text for
        you. Researchly does neither: it reads the whole draft, shows what a careful reader would notice, and leaves
        every change to you.
      </p>
      <ul className="why-list">
        <li>
          <strong>The same answer every time.</strong> The engine is deterministic rules, not a language model, so a
          draft checked twice gets the same feedback twice.
        </li>
        <li>
          <strong>A source for every suggestion.</strong> Each flag says what was noticed, why it matters and where
          the advice comes from, so you can judge it rather than take it on trust.
        </li>
        <li>
          <strong>No AI model reads your draft.</strong> Text is processed in memory for one request and then
          dropped, and a local mode that sends nothing anywhere remains available.
        </li>
        <li>
          <strong>It never writes for you.</strong> There is no drafting, rewriting or paraphrasing, which is what
          makes it usable where generative AI is restricted.
        </li>
        <li>
          <strong>A measured false-flag rate.</strong> The checks are run against accepted theses and published
          articles, and how often they flag good writing is measured and tracked, so the noise is known rather
          than guessed.
        </li>
        <li>
          <strong>Exact checks across the whole draft.</strong> Every figure and table cited, every abbreviation
          defined once, numbers in the text matching the table, and advice that changes with the section, since
          the passive voice in Methods is not a fault.
        </li>
      </ul>
      <p className="why-for">
        Researchly is for early-career researchers and for anyone writing in English as a second language. It teaches
        the conventions of research writing while you write, and it encourages you to do the writing yourself.
      </p>
    </section>
  );
}
