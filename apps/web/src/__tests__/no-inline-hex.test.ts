import { readdirSync, readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, relative } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Brand guardrail: colour lives only in the design tokens.
 *
 * `styles/tokens.css` is the single place a raw colour value is allowed. Every
 * component and every other stylesheet must reference a token via var(), never a
 * hex literal. Enforced now, while there is almost no UI and it is therefore
 * cheap; once components exist, a stray hex literal is a palette leak that no
 * longer matches the brand when the token changes.
 */

const SRC = dirname(dirname(fileURLToPath(import.meta.url)));
const TOKENS_FILE = join(SRC, "styles", "tokens.css");

// Matches CSS hex colour literals: #RGB, #RGBA, #RRGGBB, #RRGGBBAA. The trailing
// negative lookahead stops #RRGGBB from being read as a shorter match.
const HEX = /#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![0-9a-fA-F])/g;

const SCANNED_EXTENSIONS = [".ts", ".tsx", ".css", ".js", ".jsx"];

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      out.push(...walk(full));
    } else if (SCANNED_EXTENSIONS.some((ext) => full.endsWith(ext))) {
      out.push(full);
    }
  }
  return out;
}

describe("no inline hex colours in apps/web/src", () => {
  it("finds no hex literal outside styles/tokens.css", () => {
    const offenders: string[] = [];
    for (const file of walk(SRC)) {
      if (file === TOKENS_FILE) continue;
      const text = readFileSync(file, "utf8");
      const matches = text.match(HEX);
      if (matches) {
        offenders.push(`${relative(SRC, file)}: ${[...new Set(matches)].join(", ")}`);
      }
    }
    expect(
      offenders,
      `Hex colour literals must live only in styles/tokens.css. Use a var(--prov-*) token instead.\n${offenders.join("\n")}`,
    ).toEqual([]);
  });
});
