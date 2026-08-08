import { describe, expect, it, vi } from "vitest";
import { ApiError, buildUrl, createClient, readApiConfig } from "../api/client";

const config = { baseUrl: "http://api.test", apiKey: "test-key" };

function response(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

describe("buildUrl", () => {
  it("drops absent and empty query values instead of sending them blank", () => {
    expect(
      buildUrl("http://api.test", "/v1/defects", {
        code: "R07",
        station: undefined,
        severity: null,
        cursor: "",
        limit: 100,
      }),
    ).toBe("http://api.test/v1/defects?code=R07&limit=100");
  });

  it("omits the query string entirely when there is nothing to send", () => {
    expect(buildUrl("http://api.test", "/v1/stations")).toBe("http://api.test/v1/stations");
  });
});

describe("readApiConfig", () => {
  it("falls back to the documented local-dev defaults", () => {
    const resolved = readApiConfig({});
    expect(resolved.baseUrl).toBe("http://localhost:8000");
    expect(resolved.apiKey).toBe("prov-operator-key");
  });

  it("takes the environment's values and trims a trailing slash", () => {
    const resolved = readApiConfig({
      VITE_API_BASE_URL: "https://prov.example/",
      VITE_API_KEY: "real-key",
    });
    expect(resolved.baseUrl).toBe("https://prov.example");
    expect(resolved.apiKey).toBe("real-key");
  });
});

describe("createClient", () => {
  it("sends the API key header", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(response({ ok: true }));
    const client = createClient(config, fetchImpl as unknown as typeof fetch);

    await client.get("/v1/stations", { query: { limit: 10 } });

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://api.test/v1/stations?limit=10",
      expect.objectContaining({ headers: expect.objectContaining({ "X-API-Key": "test-key" }) }),
    );
  });

  it("turns an RFC 7807 problem into an ApiError that says what happened", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      response(
        {
          title: "Not Found",
          status: 404,
          detail: "No trust score for station 'STA-09'. Load a data drop first.",
          request_id: "req-42",
        },
        { status: 404 },
      ),
    );
    const client = createClient(config, fetchImpl as unknown as typeof fetch);

    await expect(client.get("/v1/trust/STA-09")).rejects.toMatchObject({
      status: 404,
      detail: "No trust score for station 'STA-09'. Load a data drop first.",
      requestId: "req-42",
    });
  });

  it("still produces a usable error when the body is not a problem document", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValue(new Response("<html>502</html>", { status: 502, statusText: "Bad Gateway" }));
    const client = createClient(config, fetchImpl as unknown as typeof fetch);

    const error = await client.get("/v1/stations").catch((caught: ApiError) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).detail).toMatch(/returned 502/);
    expect((error as ApiError).remedy).toMatch(/Retry/);
  });

  it("reports a transport failure as a network error, not a server error", async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    const client = createClient(config, fetchImpl as unknown as typeof fetch);

    const error = await client.get("/v1/stations").catch((caught: ApiError) => caught);
    expect((error as ApiError).isNetworkError).toBe(true);
    expect((error as ApiError).remedy).toMatch(/make up/);
  });

  it("lets an abort propagate rather than dressing it up as a failure", async () => {
    const abort = new DOMException("aborted", "AbortError");
    const fetchImpl = vi.fn().mockRejectedValue(abort);
    const client = createClient(config, fetchImpl as unknown as typeof fetch);

    await expect(client.get("/v1/stations")).rejects.toBe(abort);
  });
});

describe("ApiError.remedy", () => {
  const make = (status: number, requestId: string | null = null) =>
    new ApiError({ status, title: "t", detail: "d", requestId });

  it("tells an operator what to do for each failure they can act on", () => {
    expect(make(401).remedy).toMatch(/VITE_API_KEY/);
    expect(make(403).remedy).toMatch(/VITE_API_KEY/);
    expect(make(404).remedy).toMatch(/make demo/);
    expect(make(422).remedy).toMatch(/filter or time window/);
    expect(make(500, "req-9").remedy).toMatch(/req-9/);
  });

  it("never says only that something went wrong", () => {
    for (const status of [400, 401, 403, 404, 422, 500]) {
      expect(make(status).remedy.toLowerCase()).not.toContain("something went wrong");
    }
  });
});
