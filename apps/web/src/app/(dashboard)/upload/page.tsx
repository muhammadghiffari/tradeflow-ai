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
        <h1 className="text-2xl font-bold tracking-tight">Upload Documents</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Upload your B/L, Packing List, and Invoice to begin AI-powered customs processing.
        </p>
      </div>

      {/* Document slots */}
      <div className="space-y-4">
        {slots.map(({ slot, label, required, file }) => (
          <div key={slot} className="space-y-2">
            <div className="flex items-center gap-2">
              <label htmlFor={`upload-${slot}`} className="text-sm font-medium">
                {label}
              </label>
              {required && <span className="text-xs text-red-400">Required</span>}
              {!required && <span className="text-xs text-muted-foreground">Optional</span>}
            </div>

            {file ? (
              /* File preview */
              <div className="flex items-center gap-3 rounded-xl border border-green-500/30 bg-green-500/10 px-4 py-3">
                <CheckCircle2 className="h-4 w-4 text-green-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{file.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setFile(slot, null)}
                  className="text-muted-foreground hover:text-red-400 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              /* Drop zone */
              <div
                className={cn("drop-zone p-8 text-center", dragging === slot && "drag-over")}
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
                <Upload className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
                <p className="text-sm text-muted-foreground">
                  <span className="text-primary font-medium">Click to upload</span> or drag & drop
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  PDF, JPG, PNG, TIFF, XLSX · Max 50MB
                </p>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Info box */}
      <div className="rounded-xl border border-blue-500/20 bg-blue-500/10 px-4 py-3 flex items-start gap-3">
        <AlertCircle className="h-4 w-4 text-blue-400 shrink-0 mt-0.5" />
        <div className="text-xs text-muted-foreground space-y-1">
          <p>
            AI extraction begins immediately after upload. Processing typically takes{" "}
            <strong className="text-foreground">2–5 minutes</strong>.
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
          "w-full flex items-center justify-center gap-2 rounded-xl px-6 py-3.5 text-sm font-semibold transition-all duration-200",
          allRequired && !uploading
            ? "bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/25"
            : "bg-white/10 text-muted-foreground cursor-not-allowed",
        )}
      >
        {uploading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" /> Processing Upload…
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
