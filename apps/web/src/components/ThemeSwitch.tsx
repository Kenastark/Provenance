import { useTheme, type ThemePreference } from "../lib/theme";

/**
 * The dark/light/system theme control.
 *
 * Shared between `TopBar` (the operator chrome) and `SignInScreen` (which has
 * no chrome of its own to put it in) so there is exactly one control, one
 * `data-testid`, and one place that ever needs to change if the theme options
 * do. The two never render at once - `SignInGate` shows one or the other -
 * so the shared `data-testid="theme-switch"` never collides.
 */

const THEMES: { value: ThemePreference; label: string }[] = [
  { value: "dark", label: "Dark" },
  { value: "light", label: "Light" },
  { value: "system", label: "System" },
];

export interface ThemeSwitchProps {
  className?: string;
}

export function ThemeSwitch({ className = "" }: ThemeSwitchProps) {
  const { preference, setPreference } = useTheme();

  return (
    <label
      className={`flex shrink-0 items-center gap-2 text-caption text-text-tertiary ${className}`}
    >
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
  );
}
