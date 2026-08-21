import { RBAC_ENTRIES } from "../../lib/rbac";
import { ROLE_HIERARCHY, ROLE_LABELS, roleAtLeast, roleGrants, useRole } from "../../lib/role";

/**
 * The RBAC matrix: the role hierarchy, and which role each operational endpoint
 * requires. Two tables rather than one, because they answer different questions -
 * "what does a role grant" and "what does this specific action need" - and
 * collapsing them loses the hierarchy's shape (admin ⊃ operator ⊃ researcher ⊃
 * public_read), which is the more important of the two facts.
 */

export function RbacMatrix() {
  const { role: current } = useRole();

  return (
    <div className="flex flex-col gap-4" data-testid="rbac-matrix">
      <div>
        <h4 className="mb-1 text-subhead">Role hierarchy</h4>
        <p className="mb-2 text-caption text-text-tertiary">
          Each role grants everything the roles beneath it grant. There is no session or login -
          a caller's role is resolved purely from the <code>X-API-Key</code> header it sends.
        </p>
        <table className="prov-table">
          <caption className="sr-only">Role hierarchy, lowest to highest</caption>
          <thead>
            <tr>
              <th scope="col" className="py-1 text-left">
                Role
              </th>
              <th scope="col" className="py-1 text-left">
                Grants
              </th>
            </tr>
          </thead>
          <tbody>
            {ROLE_HIERARCHY.map((role) => (
              <tr key={role} data-testid="rbac-role-row" aria-current={role === current ? "true" : undefined}>
                <th scope="row" className="py-1 text-left font-normal text-text">
                  {ROLE_LABELS[role]}
                  {role === current && <span className="ml-2 text-caption text-interactive">(you)</span>}
                </th>
                <td className="py-1 text-text-secondary">{roleGrants(role)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div>
        <h4 className="mb-1 text-subhead">Operational endpoints</h4>
        <table className="prov-table">
          <caption className="sr-only">Which role each operational endpoint requires</caption>
          <thead>
            <tr>
              <th scope="col" className="py-1 text-left">
                Endpoint
              </th>
              <th scope="col" className="py-1 text-left">
                Requires
              </th>
              <th scope="col" className="py-1 text-left">
                You
              </th>
            </tr>
          </thead>
          <tbody>
            {RBAC_ENTRIES.map((entry) => {
              const reachable = roleAtLeast(current, entry.role);
              return (
                <tr key={`${entry.method} ${entry.path}`} data-testid="rbac-endpoint-row">
                  <th scope="row" className="py-1 text-left font-normal text-text">
                    <span className="font-mono text-caption text-text-tertiary">{entry.method}</span>{" "}
                    <span className="font-mono">{entry.path}</span>
                    <span className="block text-caption text-text-tertiary">{entry.description}</span>
                  </th>
                  <td className="py-1 text-text-secondary">{ROLE_LABELS[entry.role]}</td>
                  <td className={reachable ? "prov-state-verified py-1" : "prov-state-fault py-1"}>
                    {reachable ? "reachable" : "blocked"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
