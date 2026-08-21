import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
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
export const ROLE_HIERARCHY: readonly Role[] = ["public_read", "researcher", "operator", "admin"];

/** True when `current` grants at least everything `required` does. */
export function roleAtLeast(current: Role, required: Role): boolean {
  return ROLE_HIERARCHY.indexOf(current) >= ROLE_HIERARCHY.indexOf(required);
}

/** The sentence RbacMatrix renders per row: everything `role` and the roles
 * beneath it grant, joined - the one wording for "what does this role get". */
export function roleGrants(role: Role): string {
  return ROLE_HIERARCHY.slice(0, ROLE_HIERARCHY.indexOf(role) + 1)
    .map((granted) => ROLE_LABELS[granted])
    .join(" + ");
}

const STORAGE_KEY = "provenance.role";
const DEV_KEYS = new Set(Object.values(ROLE_KEYS));

function isRole(value: string | null): value is Role {
  return value === "public_read" || value === "researcher" || value === "operator" || value === "admin";
}

/** The role a dev key resolves to, or null for a real deployment's key - which
 * cannot be mapped back to a role client-side, only forwarded as-is. Exported
 * for the sign-in screen's "paste an API key" field: reusing this is what makes
 * a role card and a pasted key the same mechanism instead of two. */
export function keyToRole(key: string | undefined): Role | null {
  if (!key) return null;
  const found = (Object.entries(ROLE_KEYS) as [Role, string][]).find(([, v]) => v === key);
  return found ? found[0] : null;
}

function hasStoredRole(): boolean {
  try {
    return isRole(localStorage.getItem(STORAGE_KEY));
  } catch {
    return false;
  }
}

function clearStoredRole(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // See readStored: persistence is best-effort.
  }
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
  /** False until a role has been chosen in this browser - see SignInGate. When
   * `canSwitch` is false there is nothing to choose, so this flips to true on
   * its own right after mount rather than waiting on an interaction. */
  signedIn: boolean;
  /** Persists `next` as the chosen role and marks the browser signed in. */
  signIn: (next: Role) => void;
  /** Clears the persisted role and returns to signed-out. The dev switcher
   * (TopBar) can still pick a role for the rest of this render regardless. */
  signOut: () => void;
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
  const [signedIn, setSignedIn] = useState<boolean>(hasStoredRole);

  const setRole = useCallback((next: Role) => {
    setRoleState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // See readStored: persistence is best-effort.
    }
  }, []);

  const signIn = useCallback(
    (next: Role) => {
      setRole(next);
      setSignedIn(true);
    },
    [setRole],
  );

  const signOut = useCallback(() => {
    clearStoredRole();
    setSignedIn(false);
  }, []);

  useEffect(() => {
    if (!signedIn && !canSwitch) signIn(role);
  }, [signedIn, canSwitch, role, signIn]);

  const value = useMemo<RoleContextValue>(
    () => ({
      role,
      apiKey: canSwitch ? ROLE_KEYS[role] : (envApiKey as string),
      setRole,
      canSwitch,
      signedIn,
      signIn,
      signOut,
    }),
    [role, canSwitch, envApiKey, setRole, signedIn, signIn, signOut],
  );

  return <RoleContext.Provider value={value}>{children}</RoleContext.Provider>;
}

export function useRole(): RoleContextValue {
  const context = useContext(RoleContext);
  if (!context) throw new Error("useRole must be used inside a RoleProvider");
  return context;
}
