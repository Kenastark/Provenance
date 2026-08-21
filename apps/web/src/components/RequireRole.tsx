import type { ReactNode } from "react";
import { ROLE_LABELS, roleAtLeast, useRole, type Role } from "../lib/role";

/**
 * Route-level role gating.
 *
 * This is a UX courtesy, not the access boundary - the server's `require(Role.X)`
 * on every route is that, and answers 401/403 regardless of what this component
 * does. What this buys an operator is an honest sentence instead of a wall of
 * request errors when they land on a screen their current role does not reach.
 */

export function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const { role: current, canSwitch } = useRole();

  if (roleAtLeast(current, role)) return <>{children}</>;

  return (
    <div className="p-4">
      <div className="prov-panel p-5" role="alert" data-testid="role-forbidden">
        <p className="font-display text-subhead prov-state-fault">This screen needs a higher role</p>
        <p className="mt-2 text-body text-text">
          You are signed in as {ROLE_LABELS[current]}. This screen requires {ROLE_LABELS[role]} or
          above.
        </p>
        <p className="mt-1 text-body text-text-secondary">
          {canSwitch
            ? "Open the account menu in the top bar and switch role to continue."
            : "The API key configured for this deployment (VITE_API_KEY) does not grant that role."}
        </p>
      </div>
    </div>
  );
}
