import { NavLink } from "react-router-dom";
import { useVersion } from "../../api/queries";
import { formatRelative, formatTimestamp } from "../../lib/format";
import { ROLE_LABELS, roleAtLeast, useRole, type Role } from "../../lib/role";
import { useTheme, type ThemePreference } from "../../lib/theme";
import { TIME_WINDOWS, type TimeWindowKey } from "../../lib/timeWindow";
import { useWindowState } from "../../lib/windowContext";

/**
 * The operator chrome.
 *
 * It says "Provenance" and nothing else. The product descriptor ("AI Trust Layer
 * for Environmental Data") belongs on the login screen and the marketing surfaces;
 * the "Is This Real?" hook belongs on the demo title card. Someone who sits in
 * front of this for a shift does not need to be asked a rhetorical question every
 * time they look at the toolbar.
 *
 * The lockup is the fixed SVG asset at 56px. The wordmark is never re-set in the
 * display face - that is what the asset is for.
 */

/** `role` is the minimum role a screen needs; absent, every role reaches it. A tab
 * a role cannot reach is left off the nav rather than shown and then blocked - the
 * block message still exists (`RequireRole`) for anyone who navigates there directly
 * or follows a stale link. */
const NAV: { to: string; label: string; end: boolean; role?: Role }[] = [
  { to: "/", label: "Network map", end: true },
  { to: "/quality", label: "Data quality", end: false },
  { to: "/timeline", label: "Events", end: false },
  { to: "/evidence", label: "Evidence", end: false },
  { to: "/audit", label: "Audit report", end: false },
  { to: "/alerts", label: "Alert Centre", end: false, role: "operator" },
  { to: "/admin", label: "Admin", end: false, role: "admin" },
];

const THEMES: { value: ThemePreference; label: string }[] = [
  { value: "dark", label: "Dark" },
  { value: "light", label: "Light" },
  { value: "system", label: "System" },
];

const ROLES: Role[] = ["public_read", "researcher", "operator", "admin"];

export interface TopBarProps {
  timeWindow: TimeWindowKey;
  onTimeWindowChange: (next: TimeWindowKey) => void;
}

export function TopBar({ timeWindow, onTimeWindowChange }: TopBarProps) {
  const { preference, resolved, setPreference } = useTheme();
  const { role, setRole, canSwitch, signOut } = useRole();
  const { anchor } = useWindowState();
  const version = useVersion();
  const visibleNav = NAV.filter((item) => !item.role || roleAtLeast(role, item.role));

  // The approved lockup inks its wordmark in the brand's near-black, which
  // disappears on the dark theme - and dark is the default here. The reversed
  // lockup is the same artwork with the wordmark in --prov-white, derived from the
  // original by scripts/gen_reversed_lockup.py so the two cannot drift.
  const lockup =
    resolved === "dark"
      ? "/provenance-lockup-horizontal-reversed.svg"
      : "/provenance-lockup-horizontal.svg";

  return (
    <header
      className="flex h-8 shrink-0 flex-wrap items-center gap-4 border-b border-border bg-bg-raised px-4"
      style={{ height: "var(--prov-topbar-height)" }}
    >
      <img
        src={lockup}
        alt="Provenance"
        height={56}
        className="w-auto shrink-0"
        style={{ height: 56 }}
        data-testid="lockup"
      />

      <nav aria-label="Primary" className="ml-6 flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
        {visibleNav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              [
                "whitespace-nowrap rounded-md px-3 py-2 text-body",
                isActive
                  ? "bg-surface text-interactive"
                  : "text-text-secondary hover:bg-surface-hover hover:text-text",
              ].join(" ")
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Deliberately the one place freshness is measured against the real wall
          clock rather than the dataset's own anchor: this answers "is the pipeline
          itself live right now", a whole-network fact, not "did this station fall
          behind its peers" (what the station drawer's "last reading" shows, and
          which stays anchor-relative on purpose - see lib/format.ts's formatRelative
          doc comment). A frozen historical drop reads as increasingly old here,
          honestly, rather than every station masking that fact by looking current
          relative only to itself. */}
      {anchor && (
        <p
          className="shrink-0 whitespace-nowrap text-caption text-text-tertiary"
          data-testid="data-freshness"
          title={`Newest ingested reading: ${formatTimestamp(anchor.toISOString())}`}
        >
          Data as of {formatTimestamp(anchor.toISOString())} ({formatRelative(anchor.toISOString())})
        </p>
      )}

      <label className="flex shrink-0 items-center gap-2 text-caption text-text-tertiary">
        <span>Window</span>
        <select
          className="prov-input"
          value={timeWindow}
          onChange={(event) => onTimeWindowChange(event.target.value as TimeWindowKey)}
        >
          {TIME_WINDOWS.map((option) => (
            <option key={option.key} value={option.key}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

      <label className="flex shrink-0 items-center gap-2 text-caption text-text-tertiary">
        <span>Theme</span>
        <select
          className="prov-input"
          value={preference}
          onChange={(event) => setPreference(event.target.value as ThemePreference)}
          data-testid="theme-switch"
        >
          {THEMES.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

      <details className="relative shrink-0">
        <summary
          className="prov-button list-none"
          aria-label="Account and build information"
          data-testid="account-menu"
        >
          {ROLE_LABELS[role]}
        </summary>
        <div className="prov-panel absolute right-0 z-drawer mt-2 w-full min-w-0 p-3 text-caption shadow-overlay">
          <p className="text-text-secondary">
            Signed in as <span className="text-text">{ROLE_LABELS[role]}</span> (local API key). A
            role is resolved from the <code>X-API-Key</code> header sent with every request - there
            is no separate login.
          </p>
          {canSwitch ? (
            <label className="mt-3 flex items-center gap-2">
              <span className="text-text-tertiary">Role (dev)</span>
              <select
                className="prov-input"
                value={role}
                onChange={(event) => setRole(event.target.value as Role)}
                data-testid="role-switch"
              >
                {ROLES.map((option) => (
                  <option key={option} value={option}>
                    {ROLE_LABELS[option]}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <p className="mt-2 text-text-tertiary">
              This deployment pins a fixed API key (VITE_API_KEY); role switching is disabled.
            </p>
          )}
          <button type="button" className="prov-button mt-3 w-full" onClick={signOut} data-testid="sign-out">
            Sign out
          </button>
          {version.data && (
            <dl className="mt-3 space-y-1 font-mono text-micro text-text-tertiary">
              <div className="flex justify-between gap-3">
                <dt>version</dt>
                <dd>{version.data.version}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt>git</dt>
                <dd>{version.data.git_sha.slice(0, 10)}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt>config</dt>
                <dd>{version.data.config_hash.slice(0, 10)}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt>trust cfg</dt>
                <dd>{version.data.trust_config_hash.slice(0, 10)}</dd>
              </div>
            </dl>
          )}
        </div>
      </details>
    </header>
  );
}
