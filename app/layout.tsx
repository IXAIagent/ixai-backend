import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "一玄 IXAI Agent｜AI 投資監控系統",
  description:
    "IXAI Agent 結合多資產部位追蹤、FCN 風險監控、Crypto 策略追蹤與 AI Morning Brief。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-Hant">
      <body>{children}</body>
    </html>
  );
}
