import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

/**
 * Theme state.
 *
 * Dark is the default because this is a map-first operations screen that people
 * sit in front of for a shift. Light is a full implementation, not an inversion:
 * the token file redefines the state colours for light because Sentinel Green and
 * Alert Amber at their core values do not pass contrast as text on white.
 *
 * The choice is persisted, and "system" is a real third option rather than an
 * absent one, so the dashboard follows an operator's OS setting if they want.
 */

export type ThemePreference = "dark" | "light" | "system";
export type ResolvedTheme = "dark" | "light";

const STORAGE_KEY = "provenance.theme";

interface ThemeContextValue {
  preference: ThemePreference;
  resolved: ResolvedTheme;
  setPreference: (next: ThemePreference) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function readStored(): ThemePreference {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === "dark" || raw === "light" || raw === "system") return raw;
  } catch {
    // Private-browsing or a locked-down profile can throw on localStorage access.
    // A theme preference is not worth failing a render over.
  }
  return "dark";
}

function systemTheme(): ResolvedTheme {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: light)").matches
    ? "light"
    : "dark";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>(readStored);
  const [systemResolved, setSystemResolved] = useState<ResolvedTheme>(systemTheme);

  useEffect(() => {
    const media = window.matchMedia?.("(prefers-color-scheme: light)");
    if (!media) return;
    const onChange = () => setSystemResolved(media.matches ? "light" : "dark");
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  const resolved: ResolvedTheme = preference === "system" ? systemResolved : preference;

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", resolved);
  }, [resolved]);

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // See readStored: persistence is best-effort.
    }
  }, []);

  const value = useMemo(
    () => ({ preference, resolved, setPreference }),
    [preference, resolved, setPreference],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used inside a ThemeProvider");
  return context;
}
