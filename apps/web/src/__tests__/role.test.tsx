import { renderHook } from "@testing-library/react";
import { act } from "react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { ROLE_KEYS, RoleProvider, roleAtLeast, useRole } from "../lib/role";

function wrapperWith(envApiKey: string | undefined) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <RoleProvider envApiKey={envApiKey}>{children}</RoleProvider>;
  };
}

describe("roleAtLeast", () => {
  it("says every role grants itself", () => {
    expect(roleAtLeast("public_read", "public_read")).toBe(true);
    expect(roleAtLeast("admin", "admin")).toBe(true);
  });

  it("mirrors the backend hierarchy: admin ⊃ operator ⊃ researcher ⊃ public_read", () => {
    expect(roleAtLeast("admin", "operator")).toBe(true);
    expect(roleAtLeast("admin", "researcher")).toBe(true);
    expect(roleAtLeast("admin", "public_read")).toBe(true);
    expect(roleAtLeast("operator", "admin")).toBe(false);
    expect(roleAtLeast("researcher", "operator")).toBe(false);
    expect(roleAtLeast("public_read", "researcher")).toBe(false);
  });
});

describe("RoleProvider", () => {
  it("defaults to operator, matching the client's DEFAULT_API_KEY", () => {
    const { result } = renderHook(() => useRole(), { wrapper: wrapperWith(undefined) });
    expect(result.current.role).toBe("operator");
    expect(result.current.apiKey).toBe(ROLE_KEYS.operator);
    expect(result.current.canSwitch).toBe(true);
  });

  it("initialises from a documented dev key in VITE_API_KEY", () => {
    const { result } = renderHook(() => useRole(), { wrapper: wrapperWith("prov-admin-key") });
    expect(result.current.role).toBe("admin");
  });

  it("switches role and updates the resolved api key", () => {
    const { result } = renderHook(() => useRole(), { wrapper: wrapperWith(undefined) });
    act(() => result.current.setRole("admin"));
    expect(result.current.role).toBe("admin");
    expect(result.current.apiKey).toBe(ROLE_KEYS.admin);
  });

  it("pins the key and disables switching when VITE_API_KEY is not one of the four dev keys", () => {
    const { result } = renderHook(() => useRole(), { wrapper: wrapperWith("a-real-deployment-key") });
    expect(result.current.canSwitch).toBe(false);
    expect(result.current.apiKey).toBe("a-real-deployment-key");
  });
});
