import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { useVersion } from "../../api/queries";
import { ThemeSwitch } from "../../components/ThemeSwitch";
import { formatRelative, formatTimestamp } from "../../lib/format";
import { ROLE_LABELS, roleAtLeast, useRole, type Role } from "../../lib/role";
import { useTheme } from "../../lib/theme";
import { TIME_WINDOWS, type TimeWindowKey } from "../../lib/timeWindow";
import { useWindowState } from "../../lib/windowContext";

/**
 * The operator chrome.
 *
 * It says "Provenance" and nothing else. The product descriptor ("An AI trust
 * layer for Environmental Sensor Networks.") belongs on the login screen and the
 * marketing surfaces; the "Is This Real?" hook belongs on the demo title card.
 * Someone who sits in front of this for a shift does not need to be asked a
 * rhetorical question every time they look at the toolbar.
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

const ROLES: Role[] = ["public_read", "researcher", "operator", "admin"];

/**
 * The bar's right-hand half: nav, window picker, theme, account.
 *
 * One DOM tree, two layouts. From `xl` up it is a flex row sitting in the bar
 * exactly as it always was; below `xl` the same elements become a dropdown panel
 * hanging off the bottom of the bar. Rendering it twice - once "desktop", once
 * "mobile" - would have been easier to read and wrong: every nav link would exist
 * twice, so `getByRole("link", { name: "Admin" })` starts throwing on a duplicate
 * match, and a screen reader would announce the whole chrome twice.
 *
 * `xl` rather than `lg`: seven nav items, the window control, the theme switch and
 * the account menu need roughly 1200px before they stop crowding each other, which
 * is well above where the map/drawer split (`lg`) wants to change.
 */
const CHROME_LAYOUT = [
  "absolute inset-x-0 top-full max-h-[calc(100dvh_-_var(--prov-topbar-height))] flex-col items-stretch",
  "gap-3 overflow-y-auto border-b border-border bg-bg-raised p-4 shadow-overlay",
  "xl:static xl:flex xl:max-h-none xl:flex-1 xl:flex-row xl:items-center xl:gap-4",
  "xl:overflow-visible xl:border-0 xl:p-0 xl:shadow-none",
].join(" ");

export interface TopBarProps {
  timeWindow: TimeWindowKey;
  onTimeWindowChange: (next: TimeWindowKey) => void;
}

export function TopBar({ timeWindow, onTimeWindowChange }: TopBarProps) {
  const { resolved } = useTheme();
  const { role, setRole, canSwitch, signOut } = useRole();
  const { anchor } = useWindowState();
  const version = useVersion();
  const [menuOpen, setMenuOpen] = useState(false);
  const visibleNav = NAV.filter((item) => !item.role || roleAtLeast(role, item.role));

  // A dropdown that can only be dismissed by the control that opened it is a trap
  // on a phone, where that control is a 44px square at the top of a full-height
  // panel. Escape and a tap outside both close it; so does following a link.
  useEffect(() => {
    if (!menuOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [menuOpen]);

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
      // `relative` anchors the dropdown to the bar; the stacking context it opens
      // at z-overlay keeps both the bar and its panel above the dismiss backdrop.
      className="relative z-overlay flex shrink-0 items-center gap-4 border-b border-border bg-bg-raised px-4"
      style={{ height: "var(--prov-topbar-height)" }}
    >
      <img
        src={lockup}
        alt="Provenance"
        height={56}
        className="w-auto shrink-0"
        // The token carries the compact height below `lg`, so the mark scales with
        // the bar instead of being re-set smaller in a second place.
        style={{ height: "var(--prov-lockup-height)" }}
        data-testid="lockup"
      />

      <button
        type="button"
        className="prov-button ml-auto shrink-0 xl:hidden"
        aria-expanded={menuOpen}
        aria-controls="topbar-chrome"
        aria-label={menuOpen ? "Close menu" : "Open menu"}
        onClick={() => setMenuOpen((open) => !open)}
        data-testid="topbar-menu-toggle"
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          aria-hidden="true"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        >
          {menuOpen ? (
            <>
              <line x1="4" y1="4" x2="12" y2="12" />
              <line x1="12" y1="4" x2="4" y2="12" />
            </>
          ) : (
            <>
              <line x1="2.5" y1="4" x2="13.5" y2="4" />
              <line x1="2.5" y1="8" x2="13.5" y2="8" />
              <line x1="2.5" y1="12" x2="13.5" y2="12" />
            </>
          )}
        </svg>
      </button>

      {menuOpen && (
        <div
          className="fixed inset-0 z-drawer xl:hidden"
          onClick={() => setMenuOpen(false)}
          data-testid="topbar-menu-backdrop"
        />
      )}

      <div id="topbar-chrome" className={`${menuOpen ? "flex" : "hidden"} ${CHROME_LAYOUT}`}>
        <nav
          aria-label="Primary"
          className="flex min-w-0 flex-col items-stretch gap-1 xl:ml-6 xl:flex-1 xl:flex-row xl:items-center xl:overflow-x-auto"
        >
          {visibleNav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              style={{ fontSize: "12px" }}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) =>
                [
                  // The min-height is the touch target; from `xl` it is released and
                  // the link renders exactly as it did before - a flex item is
                  // blockified either way, so `xl:block` is the computed default.
                  "flex min-h-[var(--prov-row-height)] items-center whitespace-nowrap rounded-md px-3 py-2",
                  "xl:block xl:min-h-0",
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

        <label className="relative flex shrink-0 flex-col items-stretch gap-2 text-caption text-text-tertiary xl:flex-row xl:items-center">
          <span>Window</span>
          <select
            className="prov-input w-full xl:w-auto"
            value={timeWindow}
            onChange={(event) => onTimeWindowChange(event.target.value as TimeWindowKey)}
          >
            {TIME_WINDOWS.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </select>

          {/* Deliberately the one place freshness is measured against the real wall
            clock rather than the dataset's own anchor: this answers "is the pipeline
            itself live right now", a whole-network fact, not "did this station fall
            behind its peers" (what the station drawer's "last reading" shows, and
            which stays anchor-relative on purpose - see lib/format.ts's formatRelative
            doc comment). A frozen historical drop reads as increasingly old here,
            honestly, rather than every station masking that fact by looking current
            relative only to itself. Absolutely positioned under the window control
            so it doesn't add to the header's fixed height - but only from `xl`,
            which is where that fixed height has to be protected. Inside the
            dropdown it is an ordinary line of flow: the panel grows to fit, and an
            absolutely positioned one would land on top of the theme switch. */}
          {anchor && (
            <p
              className="whitespace-nowrap text-text-tertiary xl:absolute xl:left-0 xl:top-full xl:mt-0.5"
              style={{ fontSize: "8px" }}
              data-testid="data-freshness"
              title={`Newest ingested reading: ${formatTimestamp(anchor.toISOString())}`}
            >
              Data as of {formatTimestamp(anchor.toISOString())} ({formatRelative(anchor.toISOString())})
            </p>
          )}
        </label>

        <ThemeSwitch />
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
      </div>
    </header>
  );
}
