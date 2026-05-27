import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { Toaster } from "sonner";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: { default: "TradeFlow AI", template: "%s | TradeFlow AI" },
  description: "Predictive Customs Intelligence Platform — Cikarang Dry Port",
  keywords: ["customs", "CEISA", "import", "DJBC", "bea cukai", "AI"],
};

export const viewport: Viewport = {
  themeColor: "#0a0f1e",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} font-sans antialiased`}>
        {children}
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: "hsl(222 40% 8%)",
              border: "1px solid hsl(222 35% 18%)",
              color: "hsl(210 40% 95%)",
            },
          }}
        />
      </body>
    </html>
  );
}
