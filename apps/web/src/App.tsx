/**
 * Placeholder shell. The real dashboard lands in phase 3.
 *
 * It exists now so the toolchain, the design tokens, and the test runner are all
 * proven on a fresh clone before any UI is written.
 */
export function App() {
  return (
    <main className="shell">
      <header className="bar">
        <img src="/provenance-mark.svg" alt="" width={28} height={28} />
        <span className="wordmark">Provenance</span>
        <span className="descriptor">AI Trust Layer for Environmental Data</span>
      </header>
      <section className="stage">
        <h1>Dashboard lands in phase 3.</h1>
        <p>
          Phases 1 and 2 build the audit engine and the API. This shell is here to prove the
          toolchain and the design tokens work end to end.
        </p>
      </section>
    </main>
  );
}
