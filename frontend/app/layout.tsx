import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Backtester — NSE Options Engine",
  description:
    "Open-source backtesting engine for NSE options traders. Built for Upstox historical data.",
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
