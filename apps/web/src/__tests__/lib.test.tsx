import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  formatCount,
  formatDurationHours,
  formatMeasurement,
  formatPercent,
  formatRateAsPercent,
  formatRelative,
  formatTimestamp,
  formatTrust,
  stationShortLabel,
  toDate,
} from "../lib/format";
import {
  clearQueue,
  listQueuedActions,
  queueAction,
  queuedActionsFor,
  resetQueueCache,
  subscribeToQueue,
} from "../lib/queue";
import {
  DEFAULT_TIME_WINDOW,
  resolveWindow,
  timeWindowOption,
  withinWindow,
} from "../lib/timeWindow";

describe("format", () => {
  it("shows an em dash rather than a zero for a missing number", () => {
    expect(formatCount(null)).toBe("—");
    expect(formatTrust(undefined)).toBe("—");
    expect(formatPercent(Number.NaN)).toBe("—");
    expect(formatMeasurement(null, "µg/m3")).toBe("—");
    expect(formatDurationHours(null)).toBe("—");
    expect(formatTimestamp(null)).toBe("—");
  });

  it("keeps trust to two places so a column stays aligned", () => {
    expect(formatTrust(0.5)).toBe("0.50");
    expect(formatTrust(0.123456)).toBe("0.12");
  });

  it("renders a rate in [0,1] as a percentage", () => {
    expect(formatRateAsPercent(0.20199)).toBe("20.199%");
  });

  it("scales measurement precision to magnitude", () => {
    expect(formatMeasurement(3000, "µg/m3")).toBe("3000 µg/m3");
    expect(formatMeasurement(41.234, "µg/m3")).toBe("41.23 µg/m3");
    expect(formatMeasurement(0.00123)).toBe("0.0012");
  });

  it("reads a naive API timestamp as UTC, not as local time", () => {
    // Date.parse would treat a bare "2026-05-01T12:00:00" as local, shifting every
    // timestamp on screen by the viewer's offset.
    expect(toDate("2026-05-01T12:00:00")?.toISOString()).toBe("2026-05-01T12:00:00.000Z");
    expect(toDate("2026-05-01T12:00:00Z")?.toISOString()).toBe("2026-05-01T12:00:00.000Z");
    expect(toDate("not a date")).toBeNull();
  });

  it("labels the timestamp it displays as UTC", () => {
    expect(formatTimestamp("2026-05-01T12:00:00")).toMatch(/UTC$/);
  });

  it("speaks relative time in the units a human would", () => {
    const now = new Date("2026-05-10T12:00:00Z");
    expect(formatRelative("2026-05-10T11:59:30", now)).toMatch(/second/);
    expect(formatRelative("2026-05-10T11:30:00", now)).toMatch(/minute/);
    expect(formatRelative("2026-05-10T06:00:00", now)).toMatch(/hour/);
    expect(formatRelative("2026-05-01T12:00:00", now)).toMatch(/day/);
  });

  it("shortens a station id for tight chrome", () => {
    expect(stationShortLabel("DEB-KER11")).toBe("ER11");
    expect(stationShortLabel("STA-01")).toBe("01");
  });

  it("says durations the way the reason-code sentences do", () => {
    expect(formatDurationHours(0.5)).toBe("30 min");
    expect(formatDurationHours(12)).toBe("12 h");
    expect(formatDurationHours(336)).toBe("14 days");
  });
});

describe("time window", () => {
  const anchor = new Date("2026-05-15T00:00:00Z");

  it("anchors to the data, not to the wall clock", () => {
    const resolved = resolveWindow("24h", anchor);
    expect(resolved.start).toBe("2026-05-14T00:00:00.000Z");
    expect(resolved.end).toBe("2026-05-15T00:00:00.000Z");
  });

  it("leaves the full corpus unbounded", () => {
    const resolved = resolveWindow("corpus", anchor);
    expect(resolved.start).toBeNull();
    expect(resolved.end).toBeNull();
  });

  it("is unbounded when no data has been loaded to anchor on", () => {
    expect(resolveWindow("7d", null).start).toBeNull();
  });

  it("defaults to a bounded window", () => {
    expect(timeWindowOption(DEFAULT_TIME_WINDOW).hours).not.toBeNull();
  });

  it("falls back to the last option for an unknown key", () => {
    expect(timeWindowOption("nonsense" as never).key).toBe("corpus");
  });

  it("tests membership inclusively at both ends", () => {
    const resolved = resolveWindow("24h", anchor);
    expect(withinWindow("2026-05-14T00:00:00", resolved)).toBe(true);
    expect(withinWindow("2026-05-15T00:00:00", resolved)).toBe(true);
    expect(withinWindow("2026-05-13T23:00:00", resolved)).toBe(false);
    expect(withinWindow(null, resolved)).toBe(false);
    expect(withinWindow("nonsense", resolved)).toBe(false);
  });

  it("accepts everything when the window is unbounded", () => {
    expect(withinWindow("1999-01-01T00:00:00", resolveWindow("corpus", anchor))).toBe(true);
  });
});

describe("action queue", () => {
  beforeEach(() => {
    resetQueueCache();
    clearQueue();
  });

  it("records what was on screen when the operator acted", () => {
    const now = new Date("2026-05-15T09:00:00Z");
    const action = queueAction({
      kind: "dispatch",
      stationId: "STA-03",
      reasonCodes: ["R07"],
      note: "checked by hand",
      now,
    });

    expect(action).toMatchObject({
      kind: "dispatch",
      stationId: "STA-03",
      reasonCodes: ["R07"],
      note: "checked by hand",
      queuedAt: now.toISOString(),
    });
  });

  it("keeps the newest action first and filters by station", () => {
    queueAction({ kind: "acknowledge", stationId: "STA-01", id: "a" });
    queueAction({ kind: "dispatch", stationId: "STA-02", id: "b" });

    expect(listQueuedActions().map((action) => action.id)).toEqual(["b", "a"]);
    expect(queuedActionsFor("STA-01").map((action) => action.id)).toEqual(["a"]);
  });

  it("notifies subscribers and stops on unsubscribe", () => {
    const listener = vi.fn();
    const unsubscribe = subscribeToQueue(listener);

    queueAction({ kind: "acknowledge", stationId: "STA-01" });
    expect(listener).toHaveBeenCalledTimes(1);

    unsubscribe();
    queueAction({ kind: "acknowledge", stationId: "STA-02" });
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("survives storage being unavailable", () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota");
    });
    expect(() => queueAction({ kind: "acknowledge", stationId: "STA-01" })).not.toThrow();
    expect(listQueuedActions()).toHaveLength(1);
    setItem.mockRestore();
  });

  it("has no transport out: the module exports no send function", async () => {
    // Standing rule 5, expressed as a test. Until phase 7 records a human sign-off,
    // there is deliberately no code path from this queue to anything public.
    const queue = await import("../lib/queue");
    const names = Object.keys(queue);
    expect(names.some((name) => /send|dispatchTo|publish|post|notify/i.test(name))).toBe(false);
  });
});

describe("window anchoring", () => {
  it("anchors on the newest reading, not on when the audit happened", async () => {
    const { renderHook, waitFor } = await import("@testing-library/react");
    const { Providers } = await import("../test/harness");
    const { useWindowState } = await import("../lib/windowContext");
    const fixtures = await import("../test/fixtures");

    const { result } = renderHook(() => useWindowState(), {
      wrapper: ({ children }) => <Providers>{children}</Providers>,
    });

    // The run was generated at 2026-05-15, but the newest reading is 2026-05-14T23:00.
    // A May corpus audited in August must not produce an empty trailing week.
    await waitFor(() => expect(result.current.anchor).not.toBeNull());
    expect(result.current.anchor?.toISOString()).toBe("2026-05-14T23:00:00.000Z");
    expect(fixtures.auditRun().generated_at).toBe("2026-05-15T00:00:00");
  });

  it("falls back to the run time when no readings exist to anchor on", async () => {
    const { renderHook, waitFor } = await import("@testing-library/react");
    const { Providers } = await import("../test/harness");
    const { useWindowState } = await import("../lib/windowContext");
    const fixtures = await import("../test/fixtures");

    const { result } = renderHook(() => useWindowState(), {
      wrapper: ({ children }) => (
        <Providers
          routes={{
            "/v1/quality/summary": {
              audit_run_id: "run-2026-05-15",
              stations: [fixtures.qualityStation({ last_reading_at: null })],
            },
          }}
        >
          {children}
        </Providers>
      ),
    });

    await waitFor(() => expect(result.current.anchor).not.toBeNull());
    expect(result.current.anchor?.toISOString()).toBe("2026-05-15T00:00:00.000Z");
  });
});
