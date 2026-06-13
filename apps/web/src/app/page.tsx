import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center px-4 py-12">
      <div className="max-w-3xl rounded-3xl border border-white/10 bg-slate-900/80 p-10 shadow-2xl shadow-black/30 backdrop-blur-xl">
        <h1 className="text-4xl font-semibold tracking-tight">TradeFlow AI</h1>
        <p className="mt-4 text-lg text-slate-400">
          Predictive Customs Intelligence for CEISA 4.0. Manage declarations, monitor risk, and
          review AI-assisted extraction workflows.
        </p>
        <div className="mt-8 flex flex-col gap-4 sm:flex-row">
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center rounded-full bg-cyan-500 px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400"
          >
            Go to Dashboard
          </Link>
          <Link
            href="/api/auth/signin"
            className="inline-flex items-center justify-center rounded-full border border-slate-700 px-6 py-3 text-sm font-semibold text-slate-100 transition hover:border-slate-500"
          >
            Sign in
          </Link>
        </div>
      </div>
    </main>
  );
}
