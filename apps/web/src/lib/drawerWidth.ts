import { useCallback, useMemo, useState } from "react";

/**
 * Persisted, clamped width for a slide-over side panel (the station detail
 * drawer, the alert detail panel).
 *
 * The default lives in a CSS token (design/tokens/tokens.css), not duplicated
 * here as a literal - reading it at runtime means a future token change and a
 * "reset to default" both stay correct without touching this file. Each panel
 * gets its own token and its own storage key via `DrawerWidthConfig` so the two
 * drawers resize independently.
 *
 * Only the `lg` layout resizes: below `lg` a drawer is stacked full-width and a
 * pixel width is meaningless, so callers gate rendering the handle on that
 * breakpoint themselves.
 */

export const DRAWER_MIN_WIDTH = 360;
export const DRAWER_MAX_VIEWPORT_RATIO = 0.6;

export interface DrawerWidthConfig {
  /** CSS custom property (set on :root) carrying this panel's default width. */
  tokenVar: string;
  /** localStorage key this panel's custom width is persisted under. */
  storageKey: string;
  /** Used only if the token cannot be read (e.g. no `window`, or unset). */
  fallbackDefault: number;
}

export const STATION_DRAWER_WIDTH_CONFIG: DrawerWidthConfig = {
  tokenVar: "--prov-drawer-width",
  storageKey: "provenance.drawer-width",
  fallbackDefault: 380,
};

export const ALERT_DRAWER_WIDTH_CONFIG: DrawerWidthConfig = {
  tokenVar: "--prov-alert-drawer-width",
  storageKey: "provenance.alert-drawer-width",
  fallbackDefault: 420,
};

export function readTokenDefaultWidth(config: DrawerWidthConfig = STATION_DRAWER_WIDTH_CONFIG): number {
  if (typeof window === "undefined") return config.fallbackDefault;
  const raw = getComputedStyle(document.documentElement).getPropertyValue(config.tokenVar);
  const parsed = Number.parseFloat(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : config.fallbackDefault;
}

/** The widest a drawer may ever be: whatever sits beside it must stay visible. */
export function maxDrawerWidth(viewportWidth: number): number {
  return Math.max(DRAWER_MIN_WIDTH, Math.round(viewportWidth * DRAWER_MAX_VIEWPORT_RATIO));
}

export function clampDrawerWidth(width: number, viewportWidth: number): number {
  const max = maxDrawerWidth(viewportWidth);
  return Math.min(Math.max(width, DRAWER_MIN_WIDTH), max);
}

export function readStoredDrawerWidth(config: DrawerWidthConfig = STATION_DRAWER_WIDTH_CONFIG): number | null {
  try {
    const raw = localStorage.getItem(config.storageKey);
    if (!raw) return null;
    const parsed = Number.parseFloat(raw);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  } catch {
    // Private-browsing or a locked-down profile can throw on localStorage access.
    // A remembered width is not worth failing a render over - see lib/theme.tsx.
    return null;
  }
}

export function writeStoredDrawerWidth(width: number, config: DrawerWidthConfig = STATION_DRAWER_WIDTH_CONFIG): void {
  try {
    localStorage.setItem(config.storageKey, String(Math.round(width)));
  } catch {
    // Best-effort, same as above.
  }
}

export function clearStoredDrawerWidth(config: DrawerWidthConfig = STATION_DRAWER_WIDTH_CONFIG): void {
  try {
    localStorage.removeItem(config.storageKey);
  } catch {
    // Best-effort, same as above.
  }
}

function currentViewportWidth(): number {
  return typeof window !== "undefined" ? window.innerWidth : 1440;
}

export interface DrawerWidthState {
  /** Resolved width in px: the persisted value, clamped to the current viewport. */
  width: number;
  /** True while a non-default width is in effect (persisted or mid-drag). */
  isCustom: boolean;
  min: number;
  max: number;
  setWidth: (next: number) => void;
  reset: () => void;
}

/** Drives a drawer's width: reads the persisted value once, clamps, persists on change. */
export function useDrawerWidth(config: DrawerWidthConfig = STATION_DRAWER_WIDTH_CONFIG): DrawerWidthState {
  const defaultWidth = useMemo(() => readTokenDefaultWidth(config), [config]);
  const [stored, setStored] = useState<number | null>(() => {
    const raw = readStoredDrawerWidth(config);
    return raw === null ? null : clampDrawerWidth(raw, currentViewportWidth());
  });

  const min = DRAWER_MIN_WIDTH;
  const max = maxDrawerWidth(currentViewportWidth());

  const setWidth = useCallback(
    (next: number) => {
      const clamped = clampDrawerWidth(next, currentViewportWidth());
      setStored(clamped);
      writeStoredDrawerWidth(clamped, config);
    },
    [config],
  );

  const reset = useCallback(() => {
    setStored(null);
    clearStoredDrawerWidth(config);
  }, [config]);

  return {
    width: stored ?? defaultWidth,
    isCustom: stored !== null,
    min,
    max,
    setWidth,
    reset,
  };
}
