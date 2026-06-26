import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Legal Drafting Copilot",
  description:
    "Turn a legal brief into a synthesised argument backed by ranked, evaluated evidence.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
