import type { Config } from "tailwindcss";

/**
 * Tailwind reads the design tokens; it never defines a value of its own.
 *
 * Every scale below resolves to a `var(--prov-*)` declared in styles/tokens.css,
 * which is a byte-identical copy of design/tokens/tokens.css (enforced by
 * tests/architecture/test_brand.py). That means a utility class cannot introduce a
 * colour, size, or radius that is not in the brand, and re-theming is a token edit
 * rather than a sweep through class names.
 *
 * There are deliberately no hex literals in this file. The palette is fixed at
 * Trust Blue (the only interactive colour), Sentinel Green (verified), Alert Amber
 * (anomaly/ambiguity), Signal Red (fault), and the cool neutral ramp.
 */

const token = (name: string) => `var(--prov-${name})`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  // The state classes are composed at runtime (`prov-state-${state}`), so the
  // content scanner cannot see them and would strip the rules it thinks are
  // unused. That is not a hypothetical: it shipped a map where every *verified*
  // station rendered in the default text colour, because "prov-state-verified"
  // happened to be the one variant no source file spelled out in full.
  safelist: [
    "prov-state-verified",
    "prov-state-degraded",
    "prov-state-fault",
    "prov-state-unknown",
  ],
  // Dark is the default for this map-first operations UI, and light is a full
  // implementation rather than an inversion. Both are driven by [data-theme] on
  // <html>, so `dark:` variants are unnecessary - the tokens already swapped.
  theme: {
    colors: {
      transparent: "transparent",
      current: "currentColor",

      bg: token("bg"),
      "bg-raised": token("bg-raised"),
      surface: token("surface"),
      "surface-hover": token("surface-hover"),
      border: token("border"),
      "border-strong": token("border-strong"),

      text: token("text"),
      "text-secondary": token("text-secondary"),
      "text-tertiary": token("text-tertiary"),
      "text-inverse": token("text-inverse"),

      // Blue is the only interactive colour.
      interactive: token("interactive"),
      "interactive-hover": token("interactive-hover"),

      // Green, amber and red are STATE. Never chrome, never interaction.
      verified: token("state-verified"),
      degraded: token("state-degraded"),
      fault: token("state-fault"),
      ambiguous: token("state-ambiguous"),
      unknown: token("state-unknown"),

      "chart-grid": token("chart-grid"),
    },
    spacing: {
      0: "0px",
      1: token("space-1"),
      2: token("space-2"),
      3: token("space-3"),
      4: token("space-4"),
      5: token("space-5"),
      6: token("space-6"),
      7: token("space-7"),
      8: token("space-8"),
      px: "1px",
      full: "100%",
    },
    borderRadius: {
      none: "0",
      sm: token("radius-sm"),
      md: token("radius-md"),
      lg: token("radius-lg"),
      full: "9999px",
    },
    fontFamily: {
      display: [token("font-display")],
      ui: [token("font-ui")],
      mono: [token("font-mono")],
    },
    fontSize: {
      "display-xl": [token("size-display-xl"), token("lh-display-xl")],
      "display-l": [token("size-display-l"), token("lh-display-l")],
      heading: [token("size-heading"), token("lh-heading")],
      subhead: [token("size-subhead"), token("lh-body")],
      body: [token("size-body"), token("lh-body")],
      data: [token("size-data"), token("lh-data")],
      code: [token("size-code"), token("lh-data")],
      caption: [token("size-caption"), token("lh-data")],
      micro: [token("size-micro"), token("lh-data")],
    },
    extend: {
      boxShadow: { overlay: token("shadow-overlay") },
      transitionTimingFunction: { prov: token("ease") },
      transitionDuration: { fast: token("duration-fast"), panel: token("duration-panel") },
      zIndex: { drawer: "40", overlay: "50", toast: "60" },
    },
  },
  plugins: [],
} satisfies Config;
