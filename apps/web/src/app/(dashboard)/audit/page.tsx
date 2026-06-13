import Link from "next/link";

export default function AuditPage() {
  return (
    <div className="p-8 space-y-6">
      <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-10 shadow-2xl shadow-black/30">
        <h1 className="text-2xl font-bold tracking-tight">Audit Trail</h1>
        <p className="mt-3 text-sm text-slate-400">
          Audit Trail is under construction. This page will display a history of actions, approvals,
          and blockchain anchors.
        </p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center rounded-full bg-cyan-500 px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400"
          >
            Back to Dashboard
          </Link>
          <Link
            href="/upload"
            className="inline-flex items-center justify-center rounded-full border border-slate-700 px-6 py-3 text-sm font-semibold text-slate-100 transition hover:border-slate-500"
          >
            Upload Docs
          </Link>
        </div>
      </div>
    </div>
  );
}
