"use client";

import { cn } from "@/lib/utils";
import { AlertCircle, CheckCircle2, FileText, Loader2, Upload, X } from "lucide-react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { toast } from "sonner";

type DocSlot = "bill_of_lading" | "packing_list" | "invoice";

interface FileSlot {
  slot: DocSlot;
  label: string;
  required: boolean;
  file: File | null;
}

const INITIAL_SLOTS: FileSlot[] = [
  { slot: "bill_of_lading", label: "Bill of Lading (B/L)", required: true, file: null },
  { slot: "packing_list", label: "Packing List", required: true, file: null },
  { slot: "invoice", label: "Commercial Invoice", required: true, file: null },
];

export default function UploadPage() {
  const router = useRouter();
  const { data: session } = useSession();
  const [slots, setSlots] = useState<FileSlot[]>(INITIAL_SLOTS);
  const [dragging, setDragging] = useState<DocSlot | null>(null);
  const [uploading, setUploading] = useState(false);
  const inputRefs = useRef<Record<DocSlot, HTMLInputElement | null>>({
    bill_of_lading: null,
    packing_list: null,
    invoice: null,
  });

  const setFile = (slot: DocSlot, file: File | null) => {
    setSlots((prev) => prev.map((s) => (s.slot === slot ? { ...s, file } : s)));
  };

  const handleDrop = (e: React.DragEvent, slot: DocSlot) => {
    e.preventDefault();
    setDragging(null);
    const file = e.dataTransfer.files[0];
    if (file) setFile(slot, file);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>, slot: DocSlot) => {
    const file = e.target.files?.[0] ?? null;
    if (file) setFile(slot, file);
  };

  const allRequired = slots.filter((s) => s.required).every((s) => s.file !== null);

  const handleSubmit = async () => {
    if (!allRequired) {
      toast.error("Please upload all required documents before proceeding.");
      return;
    }
    setUploading(true);
    try {
      const form = new FormData();
      for (const { file } of slots) {
        if (file) form.append("files", file);
      }

      // @ts-ignore — accessToken is added via NextAuth callbacks
      const accessToken = session?.accessToken;
      const headers: Record<string, string> = {};
      if (accessToken) {
        headers.Authorization = `Bearer ${accessToken}`;
      }

      const res = await fetch("/api/v1/batches", { method: "POST", body: form, headers });
      if (!res.ok) throw new Error(await res.text());
      const { batch_id } = await res.json();

      toast.success("Documents uploaded! Processing has started.");
      router.push(`/batches/${batch_id}`);
    } catch (err: unknown) {
      toast.error(`Upload failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="p-8 max-w-2xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-slate-100 to-slate-300">Upload Documents</h1>
        <p className="text-sm text-slate-400 mt-1.5 font-medium leading-relaxed">
          Upload your B/L, Packing List, and Invoice to begin AI-powered customs processing.
        </p>
      </div>

      {/* Document slots */}
      <div className="space-y-5">
        {slots.map(({ slot, label, required, file }) => (
          <div key={slot} className="space-y-2">
            <div className="flex items-center justify-between">
              <label htmlFor={`upload-${slot}`} className="text-sm font-semibold text-slate-300">
                {label}
              </label>
              {required ? (
                <span className="text-[10px] font-bold text-cyan-400 bg-cyan-500/10 px-2.5 py-0.5 rounded-full uppercase tracking-wider">Required</span>
              ) : (
                <span className="text-[10px] font-bold text-slate-500 bg-white/5 px-2.5 py-0.5 rounded-full uppercase tracking-wider">Optional</span>
              )}
            </div>

            {file ? (
              /* File preview */
              <div className="flex items-center gap-3 rounded-xl border border-green-500/20 bg-green-500/5 px-4 py-3.5 shadow-lg shadow-green-950/10 hover:border-green-500/30 transition-all duration-200">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-green-500/10 text-green-400">
                  <CheckCircle2 className="h-5 w-5 shrink-0" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-200 truncate">{file.name}</p>
                  <p className="text-xs text-slate-500 mt-0.5 font-medium">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setFile(slot, null)}
                  className="text-slate-500 hover:text-red-400 hover:bg-red-500/10 p-1.5 rounded-lg transition-all"
                  title="Remove file"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              /* Drop zone */
              <div
                className={cn(
                  "rounded-2xl border-2 border-dashed border-white/5 bg-white/[0.01] p-8 text-center transition-all duration-300 cursor-pointer hover:border-cyan-500/30 hover:bg-cyan-500/[0.02]",
                  dragging === slot && "border-cyan-400 bg-cyan-500/5 shadow-[0_0_20px_rgba(34,211,238,0.05)]",
                )}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(slot);
                }}
                onDragLeave={() => setDragging(null)}
                onDrop={(e) => handleDrop(e, slot)}
                onClick={() => inputRefs.current[slot]?.click()}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    inputRefs.current[slot]?.click();
                  }
                }}
              >
                <input
                  id={`upload-${slot}`}
                  ref={(el) => {
                    inputRefs.current[slot] = el;
                  }}
                  type="file"
                  className="hidden"
                  accept=".pdf,.jpg,.jpeg,.png,.tiff,.xlsx"
                  onChange={(e) => handleFileInput(e, slot)}
                />
                <Upload className="h-8 w-8 text-slate-500 mx-auto mb-3 transition-transform duration-300 group-hover:-translate-y-0.5" />
                <p className="text-sm text-slate-400 font-medium">
                  <span className="text-cyan-400 font-semibold hover:underline">Click to upload</span> or drag & drop
                </p>
                <p className="text-xs text-slate-500 mt-1 font-medium">
                  PDF, JPG, PNG, TIFF, XLSX · Max 50MB
                </p>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Info box */}
      <div className="rounded-xl border border-blue-500/15 bg-blue-500/5 px-4 py-3.5 flex items-start gap-3">
        <AlertCircle className="h-4 w-4 text-blue-400 shrink-0 mt-0.5" />
        <div className="text-xs text-slate-400 space-y-1.5 font-medium leading-relaxed">
          <p>
            AI extraction begins immediately after upload. Processing typically takes{" "}
            <strong className="text-slate-200 font-semibold">2–5 minutes</strong>.
          </p>
          <p>
            Documents are encrypted in transit and at rest. Audit trail is anchored on Polygon
            blockchain.
          </p>
        </div>
      </div>

      {/* Submit */}
      <button
        type="button"
        onClick={handleSubmit}
        disabled={!allRequired || uploading}
        className={cn(
          "w-full flex items-center justify-center gap-2 rounded-xl px-6 py-4 text-sm font-semibold transition-all duration-300",
          allRequired && !uploading
            ? "bg-cyan-500 text-slate-950 hover:bg-cyan-400 shadow-lg shadow-cyan-500/10 hover:scale-[1.01] active:scale-[0.99]"
            : "bg-white/5 text-slate-500 cursor-not-allowed border border-white/5",
        )}
      >
        {uploading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin text-slate-950" /> Processing Upload…
          </>
        ) : (
          <>
            <FileText className="h-4 w-4" /> Start AI Processing
          </>
        )}
      </button>
    </div>
  );
}
