# Provenance dashboard

Vite + React 18 + TypeScript (strict). Built out in phase 3.

    pnpm install
    pnpm dev        # http://localhost:5173
    pnpm test       # vitest
    pnpm typecheck

## Rules carried from the design brief

- Every colour and type value resolves to a CSS custom property in
  `src/styles/tokens.css`, which is a copy of `design/tokens/tokens.css`. Never
  inline a hex value.
- A trust score never renders without its component breakdown and at least one
  reason code. The component API should make that impossible to get wrong.
- Colour is never the only channel for state. Every status also carries a shape.
- Dark theme is the default; light is fully implemented, not an afterthought.
