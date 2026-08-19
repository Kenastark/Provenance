import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import {
  clampDrawerWidth,
  clearStoredDrawerWidth,
  DRAWER_MIN_WIDTH,
  maxDrawerWidth,
  readStoredDrawerWidth,
  readTokenDefaultWidth,
  useDrawerWidth,
  writeStoredDrawerWidth,
} from "../lib/drawerWidth";

describe("clampDrawerWidth", () => {
  it("passes an in-range width through unchanged", () => {
    expect(clampDrawerWidth(500, 1440)).toBe(500);
  });

  it("floors at the minimum, below which the component table breaks", () => {
    expect(clampDrawerWidth(100, 1440)).toBe(DRAWER_MIN_WIDTH);
    expect(clampDrawerWidth(-50, 1440)).toBe(DRAWER_MIN_WIDTH);
  });

  it("ceilings at 60% of the viewport, so the map can never be dragged away", () => {
    expect(clampDrawerWidth(5000, 1440)).toBe(maxDrawerWidth(1440));
    expect(maxDrawerWidth(1440)).toBe(Math.round(1440 * 0.6));
  });

  it("never lets the max fall below the min on a narrow viewport", () => {
    // 60% of 500px is 300px, under the 360px floor - the floor wins either way.
    expect(maxDrawerWidth(500)).toBe(DRAWER_MIN_WIDTH);
    expect(clampDrawerWidth(1000, 500)).toBe(DRAWER_MIN_WIDTH);
  });
});

describe("drawer width persistence", () => {
  beforeEach(() => localStorage.clear());

  it("round-trips a written width", () => {
    writeStoredDrawerWidth(497.8);
    expect(readStoredDrawerWidth()).toBe(498);
  });

  it("reads null when nothing has been stored", () => {
    expect(readStoredDrawerWidth()).toBeNull();
  });

  it("reads null for a corrupt stored value rather than throwing", () => {
    localStorage.setItem("provenance.drawer-width", "not-a-number");
    expect(readStoredDrawerWidth()).toBeNull();
  });

  it("forgets the width once cleared", () => {
    writeStoredDrawerWidth(450);
    clearStoredDrawerWidth();
    expect(readStoredDrawerWidth()).toBeNull();
  });
});

describe("readTokenDefaultWidth", () => {
  it("reads whatever --prov-drawer-width currently resolves to on the root element", () => {
    document.documentElement.style.setProperty("--prov-drawer-width", "444px");
    expect(readTokenDefaultWidth()).toBe(444);
    document.documentElement.style.removeProperty("--prov-drawer-width");
  });

  it("falls back to a positive number when the token is not set", () => {
    document.documentElement.style.removeProperty("--prov-drawer-width");
    expect(readTokenDefaultWidth()).toBeGreaterThan(0);
  });
});

describe("useDrawerWidth", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.style.setProperty("--prov-drawer-width", "520px");
  });

  it("starts at the token default when nothing is persisted", () => {
    const { result } = renderHook(() => useDrawerWidth());
    expect(result.current.width).toBe(520);
    expect(result.current.isCustom).toBe(false);
  });

  it("starts from a persisted width, clamped", () => {
    writeStoredDrawerWidth(9999);
    const { result } = renderHook(() => useDrawerWidth());
    expect(result.current.width).toBe(result.current.max);
    expect(result.current.isCustom).toBe(true);
  });

  it("setWidth clamps, updates state, and persists", () => {
    const { result } = renderHook(() => useDrawerWidth());
    act(() => result.current.setWidth(10));
    expect(result.current.width).toBe(DRAWER_MIN_WIDTH);
    expect(readStoredDrawerWidth()).toBe(DRAWER_MIN_WIDTH);
  });

  it("reset drops back to the token default and clears storage", () => {
    const { result } = renderHook(() => useDrawerWidth());
    act(() => result.current.setWidth(600));
    act(() => result.current.reset());
    expect(result.current.width).toBe(520);
    expect(result.current.isCustom).toBe(false);
    expect(readStoredDrawerWidth()).toBeNull();
  });
});
