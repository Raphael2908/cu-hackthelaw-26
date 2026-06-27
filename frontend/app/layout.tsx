import type { Metadata } from "next";
import "./globals.css";
import { Header } from "@/components/Header";

export const metadata: Metadata = {
  title: "Supervision Cockpit",
  description:
    "Supervise human and AI legal work. Agents surface checkable claims; the human decides.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-canvas text-ink antialiased">
        <Header />
        <main>{children}</main>
      </body>
    </html>
  );
}
