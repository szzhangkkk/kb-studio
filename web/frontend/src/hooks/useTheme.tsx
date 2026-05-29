"use client";

import { ThemeProvider as NextThemeProvider, useTheme as useNextTheme } from "next-themes";
import type { ReactNode } from "react";

export function ThemeProvider({ children }: { children: ReactNode }) {
  return (
    <NextThemeProvider
      attribute="data-theme"
      defaultTheme="dark"
      enableSystem={false}
      themes={["light", "dark"]}
    >
      {children}
    </NextThemeProvider>
  );
}

export function useTheme() {
  const { theme, setTheme } = useNextTheme();
  return {
    theme: (theme as "light" | "dark") || "dark",
    toggle: () => setTheme(theme === "dark" ? "light" : "dark"),
  };
}
