export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-6 px-8 py-16">
      <p className="text-sm font-semibold uppercase tracking-widest text-emerald-300">LedgerX</p>
      <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">Frontend is running.</h1>
      <p className="max-w-xl text-lg leading-relaxed text-slate-300">
        The development foundation is ready for the next phase of LedgerX.
      </p>
      <p className="text-sm text-slate-400">Foundation setup · No financial features enabled</p>
    </main>
  );
}
