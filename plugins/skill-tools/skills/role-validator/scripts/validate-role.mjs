import { readFileSync, existsSync } from "fs";
import { resolve, basename } from "path";

const requiredSections = ["Perspective", "Areas of expertise", "Severity calibration"];

function check(results, label, fn) {
  try {
    fn();
    results.push({ label, passed: true });
  } catch (e) {
    results.push({ label, passed: false, error: e.message });
  }
}

function getSections(content) {
  const sections = {};
  const parts = content.split(/^## /m);

  for (let i = 1; i < parts.length; i++) {
    const newlineIndex = parts[i].indexOf("\n");
    if (newlineIndex === -1) {
      // Heading on last line with no body
      sections[parts[i].trim()] = "";
      continue;
    }
    const heading = parts[i].slice(0, newlineIndex).trim();
    const body = parts[i].slice(newlineIndex + 1).trim();
    sections[heading] = body;
  }

  return sections;
}

function run(rolePath) {
  const results = [];
  const resolved = resolve(rolePath);
  const filename = basename(resolved);

  check(results, "Role file exists", () => {
    if (!existsSync(resolved)) {
      throw new Error(`Not found: ${resolved}`);
    }
  });

  if (!existsSync(resolved)) return results;

  const content = readFileSync(resolved, "utf-8");
  const lines = content.split("\n");

  // H1 must be at the top — use negative lookahead to exclude ## and deeper
  check(results, "File has a title (H1 heading) at the top", () => {
    const firstNonEmpty = lines.find((l) => l.trim().length > 0);
    if (!firstNonEmpty || !/^# (?!#).+/.test(firstNonEmpty)) {
      throw new Error("No H1 heading found at the top of the file");
    }
  });

  check(results, "Title is followed by an identity statement", () => {
    const titleIndex = lines.findIndex((l) => /^# (?!#).+/.test(l));
    if (titleIndex === -1) {
      throw new Error("Cannot check identity statement — no title found");
    }

    let identityLine = null;
    for (let i = titleIndex + 1; i < lines.length; i++) {
      if (lines[i].trim().length > 0) {
        identityLine = lines[i].trim();
        break;
      }
    }

    if (!identityLine) {
      throw new Error("No identity statement found after the title");
    }

    if (identityLine.startsWith("#")) {
      throw new Error(
        "Identity statement is missing — the title is immediately followed by another heading"
      );
    }
  });

  // Use getSections() as single source of truth for section existence and content
  const sections = getSections(content);

  for (const name of requiredSections) {
    check(results, `Has "## ${name}" section`, () => {
      if (!(name in sections)) {
        throw new Error(`Missing required section: ## ${name}`);
      }
    });
  }

  check(results, '"## Areas of expertise" has content', () => {
    const section = sections["Areas of expertise"];
    if (section === undefined || section.length === 0) {
      throw new Error('"## Areas of expertise" section is empty');
    }

    const boldItems = section.match(/\*\*[^*]+\*\*/g);
    if (!boldItems || boldItems.length === 0) {
      throw new Error(
        '"## Areas of expertise" should contain bold-labeled items (e.g. **Topic** -- description)'
      );
    }
  });

  check(results, '"## Severity calibration" has all four levels', () => {
    const section = sections["Severity calibration"];
    if (section === undefined || section.length === 0) {
      throw new Error('"## Severity calibration" section is empty');
    }

    const levels = ["Critical", "Important", "Suggestion", "Nitpick"];
    const missing = levels.filter((l) => !section.includes(`**${l}**`));

    if (missing.length > 0) {
      throw new Error(`Missing severity levels: ${missing.join(", ")}`);
    }
  });

  check(results, "Filename uses lowercase-hyphen convention", () => {
    const nameWithoutExt = filename.replace(/\.md$/, "");
    if (!/^[a-z0-9-]+$/.test(nameWithoutExt)) {
      throw new Error(
        `Filename "${filename}" should use lowercase letters, numbers, and hyphens only`
      );
    }
  });

  return results;
}

const rolePath = process.argv[2];
if (!rolePath) {
  console.error("Usage: node validate-role.mjs <path-to-role-file.md>");
  process.exit(1);
}

const results = run(rolePath);

const passed = results.filter((r) => r.passed).length;
const failed = results.filter((r) => !r.passed).length;

for (const r of results) {
  const icon = r.passed ? "\x1b[32m✓\x1b[0m" : "\x1b[31m✗\x1b[0m";
  console.log(`${icon} ${r.label}`);
  if (r.error) {
    console.log(`  ${r.error}`);
  }
}

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
