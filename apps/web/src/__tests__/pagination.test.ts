import { describe, expect, it, vi } from "vitest";
import { paginateAll } from "../api/queries";
import type { ApiClient, Page } from "../api/client";

/**
 * The cursor walk, and the truncation signal.
 *
 * A count is only a count if the walk actually reached the end. When the page cap
 * stops it early, `truncated` has to say so - the previous design left the caller
 * to infer truncation from `items.length`, which stops being true the moment a
 * page comes back short.
 */

function page(items: number[], next: string | null): Page<{ id: number }> {
  return { items: items.map((id) => ({ id })), next_cursor: next, count: items.length };
}

/** A client that returns the given pages in order, repeating the last forever. */
function pagedClient(pages: Page<{ id: number }>[]): ApiClient {
  let call = 0;
  return {
    config: { baseUrl: "http://api.test", apiKey: "k" },
    get: vi.fn(async () => {
      const result = pages[Math.min(call, pages.length - 1)];
      call += 1;
      return result as unknown;
    }),
  } as unknown as ApiClient;
}

describe("paginateAll", () => {
  it("returns every row across pages and reports no truncation when the cursor runs out", async () => {
    const client = pagedClient([page([1, 2], "c1"), page([3, 4], "c2"), page([5], null)]);

    const result = await paginateAll<{ id: number }>(client, "/v1/defects", {}, undefined);

    expect(result.items.map((r) => r.id)).toEqual([1, 2, 3, 4, 5]);
    expect(result.truncated).toBe(false);
  });

  it("stops at the cap and reports truncation when rows remain upstream", async () => {
    // Every page still offers a next_cursor, so the only thing that stops the walk
    // is the cap - which is exactly the case the caller must be told about.
    const endless = page([0], "always-more");
    const client = pagedClient([endless]);

    const result = await paginateAll<{ id: number }>(client, "/v1/defects", {}, undefined, 3);

    expect(result.items).toHaveLength(3); // one row per page, capped at 3 pages
    expect(result.truncated).toBe(true);
  });

  it("passes the cursor of each page to the next request", async () => {
    const seen: (string | undefined)[] = [];
    const client = {
      config: { baseUrl: "http://api.test", apiKey: "k" },
      get: vi.fn(async (_path: string, options: { query?: Record<string, unknown> }) => {
        seen.push(options.query?.cursor as string | undefined);
        const next = seen.length < 3 ? `cursor-${seen.length}` : null;
        return page([seen.length], next);
      }),
    } as unknown as ApiClient;

    await paginateAll<{ id: number }>(client, "/v1/defects", { code: "R01" }, undefined);

    expect(seen).toEqual([undefined, "cursor-1", "cursor-2"]);
  });
});
