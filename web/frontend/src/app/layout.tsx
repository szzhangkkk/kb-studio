import type { Metadata } from "next";
import { ThemeProvider } from "../hooks/useTheme";
import "./globals.css";

export const metadata: Metadata = {
  title: "KB-Studio // CYBER",
  description: "Cyberpunk Knowledge Base Q&A Platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" className="h-full" suppressHydrationWarning>
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=Orbitron:wght@400;500;600;700;800;900&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="h-full scanlines" suppressHydrationWarning>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
