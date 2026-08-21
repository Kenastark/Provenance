import type { Role } from "./role";

export interface RbacEntry {
  method: "GET" | "POST";
  path: string;
  role: Role;
  description: string;
}

/**
 * The operational endpoints this dashboard calls, and the role each requires.
 *
 * Mirrored by hand from the `Depends(require(Role.X))` on each router
 * (`src/provenance/api/routers/{alerts,maintenance,decision,admin}.py`), cross-
 * checked against `tests/integration/test_rbac_matrix.py` - which is the real
 * source of truth for the *whole* API, not just what this dashboard uses. There is
 * no endpoint that serves this table, so it is restated here rather than fetched,
 * and it will drift silently if a route's `require()` call changes without this
 * file changing too. Tracked as a follow-up in the phase report: an
 * `/v1/admin/rbac-matrix` endpoint would let the generator take over instead.
 */
export const RBAC_ENTRIES: readonly RbacEntry[] = [
  { method: "GET", path: "/v1/alerts", role: "operator", description: "Ranked alert list" },
  { method: "GET", path: "/v1/maintenance", role: "operator", description: "Maintenance queue" },
  {
    method: "GET",
    path: "/v1/maintenance/{item_id}",
    role: "operator",
    description: "One maintenance ticket, with history",
  },
  {
    method: "POST",
    path: "/v1/maintenance/rebuild",
    role: "operator",
    description: "Raise tickets from an audit run",
  },
  {
    method: "POST",
    path: "/v1/maintenance/{item_id}/transition",
    role: "operator",
    description: "Advance a ticket's lifecycle status",
  },
  { method: "POST", path: "/v1/decision/signoff", role: "operator", description: "Record a human sign-off" },
  {
    method: "POST",
    path: "/v1/decision/dispatch",
    role: "operator",
    description: "Dispatch a public alert (requires a valid sign-off)",
  },
  { method: "GET", path: "/v1/admin/status", role: "admin", description: "Versions, config hashes, dispatch history" },
  { method: "GET", path: "/v1/admin/model-drift", role: "admin", description: "Model-plane drift monitor" },
  { method: "POST", path: "/v1/admin/retrain", role: "admin", description: "Request a model retrain" },
] as const;
