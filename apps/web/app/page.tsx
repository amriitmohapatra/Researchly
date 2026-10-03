import { Checker } from "@/components/Checker";

/**
 * The S1 surface: paste text, see explained suggestions.
 *
 * This server component renders only static chrome. All document text lives
 * in <Checker/>, a client component that sends it straight to the engine.
 */
export default function Home() {
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to the checker
      </a>
      <header className="site-header">
        <div className="wrap header-inner">
          <p className="brand" translate="no">
            <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true" focusable="false" className="brand-mark">
              <path d="M5 4.5h9.5a4.5 4.5 0 010 9H9.5L15 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M5 4.5V20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            Researchly
          </p>
          <p className="tagline">The writing coach you&rsquo;re allowed to use. It advises; it never drafts.</p>
        </div>
      </header>
      <main id="main" className="wrap" tabIndex={-1}>
        <div className="intro">
          <h1>Check a draft</h1>
          <p className="lede">
            Section-aware feedback on research writing. Each suggestion says what it noticed, why it matters and where
            the advice comes from. You make every change yourself.
          </p>
        </div>
        <Checker />
      </main>
      <footer className="site-footer">
        <div className="wrap">
          <p>
            Researchly is confidential by design: text is processed in memory for the length of one request, then
            dropped. It is never logged, stored or used for training.
          </p>
        </div>
      </footer>
    </>
  );
}
