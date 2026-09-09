import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { ThemeSwitch } from "../../components/ThemeSwitch";
import { keyToRole, ROLE_HIERARCHY, ROLE_LABELS, roleGrants, type Role } from "../../lib/role";
import { useTheme } from "../../lib/theme";
import { HERO_ROW_WIDTH, HeroFlowVisual } from "./HeroFlowVisual";

/**
 * The screen in front of the dashboard.
 *
 * It is not a login: there is no session, and nothing here talks to the server.
 * Picking a role (or pasting a key) resolves which of the four documented dev keys
 * gets sent as `X-API-Key` on every request afterward - the exact mechanism the
 * account menu's dropdown already exposes, just fronted by a full screen instead of
 * a `<details>` the first-time visitor has no reason to open. See lib/role.tsx.
 */

export interface SignInScreenProps {
  role: Role;
  canSwitch: boolean;
  onSelectRole: (role: Role) => void;
}

export function SignInScreen({ role, canSwitch, onSelectRole }: SignInScreenProps) {
  const { resolved } = useTheme();
  const [rawKey, setRawKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const rolePickerRef = useRef<HTMLDivElement | null>(null);

  // Every mount of this screen - first load, or a return trip via "Sign out" -
  // is a fresh screen a keyboard user has not seen the layout of yet, so it takes
  // focus itself rather than leaving it wherever the previous screen left it.
  useEffect(() => {
    containerRef.current?.focus();
  }, []);

  const lockup =
    resolved === "dark"
      ? "/provenance-lockup-horizontal-reversed.svg"
      : "/provenance-lockup-horizontal.svg";

  function handleKeySubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const matched = keyToRole(rawKey.trim());
    if (!matched) {
      setError("That is not one of the API keys this deployment recognises.");
      return;
    }
    setError(null);
    onSelectRole(matched);
  }

  return (
    <div
      ref={containerRef}
      tabIndex={-1}
      className="flex h-full flex-col items-center overflow-y-auto bg-bg p-4 text-center outline-none"
      data-testid="signin-screen"
    >
      {/* Positioned to land where TopBar's own theme switch sits post-sign-in
          (measured: ~116px from the right edge, ~20px from the top, at this
          app's 1440px baseline viewport - TopBar puts the account menu to its
          right, so it isn't flush with the edge). The login button lives in the
          same fixed row, immediately to the theme switch's right.

          That measurement only describes the desktop bar. Below `lg` the bar has
          collapsed to a lockup and a menu button, so there is nothing at 116px to
          line up with, and holding the offset just pushed this row inward from a
          screen that has no width to spare. It sits in the corner instead. */}
      <div className="fixed right-3 top-3 z-drawer flex items-center gap-3 lg:right-[116px] lg:top-[20px]">
        <ThemeSwitch />
        {canSwitch && (
          <button
            type="button"
            className="prov-button"
            onClick={() => rolePickerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
            data-testid="signin-login-button"
          >
            Log in
          </button>
        )}
      </div>

      {/* `m-auto` rather than `justify-center` on the parent: when this block is
          taller than the viewport, `justify-center` on an overflow-auto flex
          parent centers by pushing half the overflow above the scrollable area,
          where a scrollbar can never reach negative offsets - the eyebrow line
          and lockup would silently become unreachable. `margin: auto` collapses
          to top-aligned, fully-scrollable flow the moment there's no free space
          left to distribute, so nothing above the fold is ever unreachable. */}
      <div className="flex w-full flex-col items-center gap-8 m-auto">
        <div className="relative flex flex-col items-center gap-4 px-4">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute left-1/2 top-0 -z-10 h-72 w-72 -translate-x-1/2 -translate-y-16 rounded-full"
            style={{
              background:
                "radial-gradient(circle, color-mix(in srgb, var(--prov-blue-500) 16%, transparent) 0%, transparent 70%)",
            }}
          />
          <span className="text-caption font-display uppercase tracking-[0.2em] text-interactive">
            Green Sentinel&rsquo;s Layer 2 AI Verification Engine
          </span>
          <div className="flex flex-col items-center gap-1">
            <img
              src={lockup}
              alt="Provenance"
              height={152}
              className="w-auto"
              style={{ height: 152 }}
              data-testid="signin-lockup"
            />
            {/* `nowrap` at 27px is ~600px of unbreakable text - three phone widths,
                clipped by #root's overflow rather than scrolled to. It wraps below
                `lg`, and the clamp reaches its 27px ceiling at any viewport from
                540px up, so every desktop width renders the measured size. */}
            <p
              className="font-display font-semibold text-text lg:whitespace-nowrap"
              style={{
                fontSize: "clamp(18px, 5vw, 27px)",
                lineHeight: "var(--prov-lh-display-l)",
              }}
            >
              An AI trust layer for Environmental Sensor Networks
            </p>
          </div>
          <div className="flex flex-col items-center gap-1">
            <p
              className="text-subhead font-display font-semibold text-text"
              style={{ maxWidth: HERO_ROW_WIDTH }}
            >
              Data without trust is just noise.
            </p>
            <p className="text-subhead text-text-secondary" style={{ maxWidth: HERO_ROW_WIDTH }}>
              Across Debrecen, Green Sentinel&rsquo;s physical sensors (Layer 1) capture raw
              environmental streams. Sitting directly above it, Provenance (Layer 2) operates as an
              AI verification engine to guarantee data authenticity. Powered by a custom HST-GAT
              architecture, we evaluate cross-sensor spatial relationships, temporal trends, and
              meteorology to audit every incoming reading. By converting raw telemetry into
              real-time, explainable trust scores, we ensure every public health warning and
              municipal policy is backed by verifiable truth, never broken hardware.
            </p>
          </div>
          <HeroFlowVisual />
        </div>

        {canSwitch ? (
          <div ref={rolePickerRef} className="flex flex-col items-center gap-6">
            <div
              role="group"
              aria-label="Choose a role"
              className="grid grid-cols-1 gap-3 sm:grid-cols-2"
              data-testid="signin-role-picker"
            >
              {ROLE_HIERARCHY.map((option) => (
                <button
                  key={option}
                  type="button"
                  className="prov-panel flex w-52 flex-col items-start gap-1 p-4 text-left hover:border-interactive"
                  onClick={() => onSelectRole(option)}
                  data-testid={`signin-role-${option}`}
                >
                  <span className="font-display text-subhead text-text">{ROLE_LABELS[option]}</span>
                  <span className="text-caption text-text-tertiary">Grants: {roleGrants(option)}</span>
                </button>
              ))}
            </div>

            <form onSubmit={handleKeySubmit} className="flex flex-col items-center gap-2">
              <label htmlFor="signin-api-key" className="text-caption text-text-tertiary">
                Or paste an API key
              </label>
              <div className="flex gap-2">
                <input
                  id="signin-api-key"
                  type="text"
                  autoComplete="off"
                  spellCheck={false}
                  className="prov-input w-64"
                  value={rawKey}
                  onChange={(event) => {
                    setRawKey(event.target.value);
                    setError(null);
                  }}
                  placeholder="prov-operator-key"
                  data-testid="signin-api-key-input"
                />
                <button type="submit" className="prov-button" data-testid="signin-api-key-submit">
                  Sign in
                </button>
              </div>
              {error && (
                <p role="alert" className="text-caption prov-state-fault" data-testid="signin-api-key-error">
                  {error}
                </p>
              )}
            </form>
          </div>
        ) : (
          <p role="status" className="text-body text-text-secondary" data-testid="signin-auto-message">
            Signed in as {ROLE_LABELS[role]}…
          </p>
        )}

        <p className="max-w-md text-caption text-text-tertiary" data-testid="signin-caption">
          A role is resolved from the <code>X-API-Key</code> header sent with every request that
          follows - there is no separate login or session.
        </p>
      </div>
    </div>
  );
}
