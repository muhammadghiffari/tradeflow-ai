import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(amount: number, currency = "USD"): string {
  return new Intl.NumberFormat("id-ID", { style: "currency", currency }).format(amount);
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("id-ID", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Jakarta",
  }).format(new Date(iso));
}

export function statusToClass(status: string): string {
  const map: Record<string, string> = {
    uploaded: "uploaded",
    preprocessing: "processing",
    ocr_running: "processing",
    validating: "processing",
    review_ready: "review",
    reviewing: "review",
    approved: "accepted",
    submitted: "processing",
    accepted: "accepted",
    rejected: "rejected",
    error: "rejected",
  };
  return map[status] ?? "uploaded";
}
