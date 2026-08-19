import { useCallback, useMemo, useState } from "react";

/**
 * Persisted, clamped width for the station detail drawer.
 *
 * The default lives in the `--prov-drawer-width` token (design/tokens/tokens.css),
 * not duplicated here as a literal - reading it at runtime means a future token
 * change and a "reset to default" both stay correct without touching this file.
 *
 * Only the `lg` layout resizes: below `lg` the drawer is stacked full-width and a
 * pixel width is meaningless, so callers gate rendering the handle on that
 * breakpoint themselves.
 */

const STORAGE_KEY = "provenance.drawer-width";
export const DRAWER_MIN_WIDTH = 360;
export const DRAWER_MAX_VIEWPORT_RATIO = 0.6;
const FALLBACK_DEFAULT_WIDTH = 380;

export function readTokenDefaultWidth(): number {
  if (typeof window === "undefined") return FALLBACK_DEFAULT_WIDTH;
  const raw = getComputedStyle(document.documentElement).getPropertyValue("--prov-drawer-width");
  const parsed = Number.parseFloat(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : FALLBACK_DEFAULT_WIDTH;
}

/** The widest the drawer may ever be: the map must stay visible beside it. */
export function maxDrawerWidth(viewportWidth: number): number {
  return Math.max(DRAWER_MIN_WIDTH, Math.round(viewportWidth * DRAWER_MAX_VIEWPORT_RATIO));
}

export function clampDrawerWidth(width: number, viewportWidth: number): number {
  const max = maxDrawerWidth(viewportWidth);
  return Math.min(Math.max(width, DRAWER_MIN_WIDTH), max);
}

export function readStoredDrawerWidth(): number | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = Number.parseFloat(raw);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  } catch {
    // Private-browsing or a locked-down profile can throw on localStorage access.
    // A remembered width is not worth failing a render over - see lib/theme.tsx.
    return null;
  }
}

export function writeStoredDrawerWidth(width: number): void {
  try {
    localStorage.setItem(STORAGE_KEY, String(Math.round(width)));
  } catch {
    // Best-effort, same as above.
  }
}

export function clearStoredDrawerWidth(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
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

/** Drives the drawer's width: reads the persisted value once, clamps, persists on change. */
export function useDrawerWidth(): DrawerWidthState {
  const defaultWidth = useMemo(readTokenDefaultWidth, []);
  const [stored, setStored] = useState<number | null>(() => {
    const raw = readStoredDrawerWidth();
    return raw === null ? null : clampDrawerWidth(raw, currentViewportWidth());
  });

  const min = DRAWER_MIN_WIDTH;
  const max = maxDrawerWidth(currentViewportWidth());

  const setWidth = useCallback((next: number) => {
    const clamped = clampDrawerWidth(next, currentViewportWidth());
    setStored(clamped);
    writeStoredDrawerWidth(clamped);
  }, []);

  const reset = useCallback(() => {
    setStored(null);
    clearStoredDrawerWidth();
  }, []);

  return {
    width: stored ?? defaultWidth,
    isCustom: stored !== null,
    min,
    max,
    setWidth,
    reset,
  };
}
