import Link from "next/link";

export default function BatchesPage() {
  return (
    <div className="p-8 space-y-6">
      <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-10 shadow-2xl shadow-black/30">
        <h1 className="text-2xl font-bold tracking-tight">Declarations</h1>
        <p className="mt-3 text-sm text-slate-400">
          This page will show customs declaration batches from your company. For now, upload documents to start a new batch.
        </p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <Link
            href="/upload"
            className="inline-flex items-center justify-center rounded-full bg-cyan-500 px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400"
          >
            Upload Documents
          </Link>
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center rounded-full border border-slate-700 px-6 py-3 text-sm font-semibold text-slate-100 transition hover:border-slate-500"
          >
            Back to Dashboard
          </Link>
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <div className="glass-card p-6">
          <h2 className="text-sm font-semibold text-slate-100">No batches yet</h2>
          <p className="mt-2 text-xs text-slate-400">
            Once documents are uploaded, this page will list your recent declarations for review and approval.
          </p>
        </div>
      </div>
    </div>
  );
}
