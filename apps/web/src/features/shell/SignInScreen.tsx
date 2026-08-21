import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { keyToRole, ROLE_HIERARCHY, ROLE_LABELS, roleGrants, type Role } from "../../lib/role";
import { useTheme } from "../../lib/theme";

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
      className="flex h-full flex-col items-center justify-center gap-8 bg-bg p-8 text-center outline-none"
      data-testid="signin-screen"
    >
      <div className="flex flex-col items-center gap-4">
        <img
          src={lockup}
          alt="Provenance"
          height={96}
          className="w-auto"
          style={{ height: 96 }}
          data-testid="signin-lockup"
        />
        <p className="max-w-md text-subhead text-text-secondary">
          AI Trust Layer for Environmental Data
        </p>
      </div>

      {canSwitch ? (
        <div className="flex flex-col items-center gap-6">
          <div
            role="group"
            aria-label="Choose a role"
            className="grid grid-cols-2 gap-3"
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
  );
}
