import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup, configure } from "@testing-library/react";

// The screens sit behind a genuine request waterfall: the audit run resolves the
// time window, the window keys the defect query, the selected defect keys the raw
// series, and each hop is a real React Query round trip. One second is not enough
// for the deepest of them, and a longer wait costs nothing when the assertion
// succeeds - findBy* returns as soon as the element appears.
configure({ asyncUtilTimeout: 5000 });

// Recharts measures its container through ResizeObserver, which jsdom does not
// implement. A stub that reports a fixed box is enough for the chart to mount and
// for the surrounding panel to be asserted; the chart's own pixels are covered by
// the Playwright visual snapshots.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;

// jsdom has no layout engine, so every element measures 0x0 and ResponsiveContainer
// renders nothing. Give it a size.
Object.defineProperty(HTMLElement.prototype, "offsetWidth", { configurable: true, value: 800 });
Object.defineProperty(HTMLElement.prototype, "offsetHeight", { configurable: true, value: 600 });

// Node defines its own experimental `localStorage` global, which is undefined
// unless the process was started with --localstorage-file, and it shadows the one
// jsdom would otherwise provide. Bare `localStorage` therefore resolves to
// undefined under the test runner while working perfectly in a browser. Install a
// minimal in-memory implementation so the theme preference and the operator action
// queue - both of which persist - are exercised for real rather than falling into
// their "storage unavailable" branches on every test.
function installMemoryStorage(): Storage {
  const entries = new Map<string, string>();
  const storage: Storage = {
    get length() {
      return entries.size;
    },
    clear: () => entries.clear(),
    getItem: (key) => entries.get(key) ?? null,
    key: (index) => [...entries.keys()][index] ?? null,
    removeItem: (key) => {
      entries.delete(key);
    },
    setItem: (key, value) => {
      entries.set(key, String(value));
    },
  };
  return storage;
}

if (typeof globalThis.localStorage === "undefined" || globalThis.localStorage === null) {
  const storage = installMemoryStorage();
  Object.defineProperty(globalThis, "localStorage", { configurable: true, value: storage });
  if (typeof window !== "undefined") {
    Object.defineProperty(window, "localStorage", { configurable: true, value: storage });
  }
}

// matchMedia backs the theme's "system" preference and the reduced-motion checks.
globalThis.matchMedia ??= ((query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  addListener: vi.fn(),
  removeListener: vi.fn(),
  dispatchEvent: vi.fn(),
})) as unknown as typeof matchMedia;

afterEach(() => {
  cleanup();
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});
