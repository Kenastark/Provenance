import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

/**
 * Role state.
 *
 * There is no login screen and no session, because the backend has neither: a
 * caller's role is resolved purely from which `X-API-Key` header it sent
 * (`src/provenance/api/auth.py`), and ADR 0010 frames this deliberately as
 * "transport, not policy" - swapping in real OIDC later changes how the header is
 * produced, not the `Role` enum or the `require(Role.X)` gate on every route.
 *
 * `ROLE_KEYS` below is that same enum paired with the same four documented
 * local-dev keys `auth.py` falls back to when `PROVENANCE_API_KEYS` is unset. A
 * real deployment sets both `PROVENANCE_API_KEYS` and `VITE_API_KEY` to something
 * not in this repository - at which point `canSwitch` is false, the account menu
 * shows the pinned key's role as fixed, and nothing in the browser can silently
 * swap out a production key for a dev one. The switcher that remains for the dev
 * keys is a demo convenience only: the access boundary is, and stays, the server's
 * `require(Role.X)` on every route, never this component.
 */

export type Role = "public_read" | "researcher" | "operator" | "admin";

export const ROLE_KEYS: Record<Role, string> = {
  admin: "prov-admin-key",
  operator: "prov-operator-key",
  researcher: "prov-researcher-key",
  public_read: "prov-public-key",
};

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Admin",
  operator: "Operator",
  researcher: "Researcher",
  public_read: "Public read",
};

/** Every role in ascending order of what it grants - mirrors `_GRANTS` in
 * `src/provenance/api/auth.py` (admin ⊃ operator ⊃ researcher ⊃ public_read). */
const HIERARCHY: readonly Role[] = ["public_read", "researcher", "operator", "admin"];

/** True when `current` grants at least everything `required` does. */
export function roleAtLeast(current: Role, required: Role): boolean {
  return HIERARCHY.indexOf(current) >= HIERARCHY.indexOf(required);
}

const STORAGE_KEY = "provenance.role";
const DEV_KEYS = new Set(Object.values(ROLE_KEYS));

function isRole(value: string | null): value is Role {
  return value === "public_read" || value === "researcher" || value === "operator" || value === "admin";
}

function keyToRole(key: string | undefined): Role | null {
  if (!key) return null;
  const found = (Object.entries(ROLE_KEYS) as [Role, string][]).find(([, v]) => v === key);
  return found ? found[0] : null;
}

function readStored(envKey: string | undefined): Role {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (isRole(raw)) return raw;
  } catch {
    // Private-browsing or a locked-down profile can throw on localStorage access.
    // A role preference is not worth failing a render over (see theme.tsx).
  }
  // The dashboard is the operator surface (client.ts), so operator is the default
  // absent any other signal, same as DEFAULT_API_KEY.
  return keyToRole(envKey) ?? "operator";
}

interface RoleContextValue {
  role: Role;
  apiKey: string;
  setRole: (next: Role) => void;
  /** False when VITE_API_KEY is pinned to a key outside the four dev keys. */
  canSwitch: boolean;
}

const RoleContext = createContext<RoleContextValue | null>(null);

export function RoleProvider({
  children,
  envApiKey = import.meta.env.VITE_API_KEY,
}: {
  children: ReactNode;
  /** Injectable for tests; production reads `VITE_API_KEY`. */
  envApiKey?: string;
}) {
  const canSwitch = !envApiKey || DEV_KEYS.has(envApiKey);
  const [role, setRoleState] = useState<Role>(() => readStored(envApiKey));

  const setRole = useCallback((next: Role) => {
    setRoleState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // See readStored: persistence is best-effort.
    }
  }, []);

  const value = useMemo<RoleContextValue>(
    () => ({
      role,
      apiKey: canSwitch ? ROLE_KEYS[role] : (envApiKey as string),
      setRole,
      canSwitch,
    }),
    [role, canSwitch, envApiKey, setRole],
  );

  return <RoleContext.Provider value={value}>{children}</RoleContext.Provider>;
}

export function useRole(): RoleContextValue {
  const context = useContext(RoleContext);
  if (!context) throw new Error("useRole must be used inside a RoleProvider");
  return context;
}
