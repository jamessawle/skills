import { readFileSync, existsSync } from "fs";
import { resolve, dirname, basename, join, sep } from "path";

function parseFrontmatter(content) {
  const match = content.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return null;

  const data = {};
  let currentParent = null;

  for (const line of match[1].split("\n")) {
    if (line.length === 0) continue;

    const isIndented = /^\s{2,}/.test(line);

    if (isIndented && currentParent !== null) {
      const trimmed = line.trim();
      const colon = trimmed.indexOf(":");
      if (colon === -1) continue;
      const key = trimmed.slice(0, colon).trim();
      const value = trimmed.slice(colon + 1).trim();
      data[currentParent][key] = value;
      continue;
    }

    currentParent = null;
    const colon = line.indexOf(":");
    if (colon === -1) continue;
    const key = line.slice(0, colon).trim();
    const value = line.slice(colon + 1).trim();

    if (value === "") {
      currentParent = key;
      data[key] = {};
    } else if (value === "true") {
      data[key] = true;
    } else if (value === "false") {
      data[key] = false;
    } else {
      data[key] = value;
    }
  }
  return data;
}

const requiredFields = ["name", "description", "license", "compatibility", "metadata"];

function extractBody(content) {
  const match = content.match(/^---\n[\s\S]*?\n---\n([\s\S]*)$/);
  if (match) return match[1];
  return content;
}

// Directories within a skill that may contain referenced files
const SKILL_SUBDIRS = ["references", "scripts", "assets"];

// Returns true for patterns that are not concrete paths (placeholders, globs, variables)
function isPlaceholderPath(p) {
  // ".." or "..." — ellipsis or parent traversal used as documentation shorthand
  if (/\.{2,}/.test(p)) return true;
  // Glob wildcards or unresolved variable references
  if (/[*?$]/.test(p)) return true;
  return false;
}

function validatePaths(skillMdPath, content) {
  const resolvedPath = resolve(skillMdPath);
  const skillDir = dirname(resolvedPath);
  const body = extractBody(content);

  const paths = new Set();

  // Match ${CLAUDE_SKILL_DIR}/... paths (in code blocks or inline)
  const claudeSkillDirRe = /\$\{CLAUDE_SKILL_DIR\}\/([\w./-]+)/g;
  for (const m of body.matchAll(claudeSkillDirRe)) {
    paths.add(m[1]);
  }

  // Match references/, scripts/, and assets/ paths not preceded by a word character
  for (const subdir of SKILL_SUBDIRS) {
    const re = new RegExp(`(?<!\\w)(${subdir}\\/[\\w./-]+)`, "gm");
    for (const m of body.matchAll(re)) {
      paths.add(m[1]);
    }
  }

  for (const p of paths) {
    if (isPlaceholderPath(p)) continue;

    const resolved = resolve(skillDir, p);
    // Ensure the path stays within the skill directory (prevent traversal)
    if (!resolved.startsWith(skillDir + sep)) continue;

    check(`referenced path exists: ${p}`, () => {
      if (!existsSync(resolved)) {
        throw new Error(`Not found: ${p} (relative to skill directory)`);
      }
    });
  }
}

const results = [];

function check(label, fn) {
  try {
    fn();
    results.push({ label, passed: true });
  } catch (e) {
    results.push({ label, passed: false, error: e.message });
  }
}

function run(skillMdPath) {
  const resolved = resolve(skillMdPath);

  check("SKILL.md exists", () => {
    if (!existsSync(resolved)) {
      throw new Error(`Not found: ${resolved}`);
    }
  });

  if (!existsSync(resolved)) return;

  const content = readFileSync(resolved, "utf-8");
  let frontmatter = null;

  check("SKILL.md has YAML frontmatter", () => {
    frontmatter = parseFrontmatter(content);
    if (!frontmatter) {
      throw new Error("No YAML frontmatter found");
    }
  });

  if (!frontmatter) return;

  check("Frontmatter has required fields", () => {
    const missing = requiredFields.filter((f) => !(f in frontmatter));
    if (missing.length > 0) {
      throw new Error(`Missing required fields: ${missing.join(", ")}`);
    }
  });

  // name validation
  check('"name" format is valid', () => {
    const name = frontmatter.name;
    if (typeof name !== "string" || name.length === 0) {
      throw new Error('"name" must be a non-empty string');
    }
    if (name.length > 64) {
      throw new Error(`"name" must be at most 64 characters, got ${name.length}`);
    }
    if (!/^[a-z0-9-]+$/.test(name)) {
      throw new Error('"name" must contain only lowercase letters (a-z), numbers, and hyphens');
    }
    if (name.startsWith("-") || name.endsWith("-")) {
      throw new Error('"name" must not start or end with a hyphen');
    }
    if (/--/.test(name)) {
      throw new Error('"name" must not contain consecutive hyphens');
    }
  });

  check('"name" matches parent directory', () => {
    const expected = basename(dirname(resolved));
    if (frontmatter.name !== expected) {
      throw new Error(`"name" is "${frontmatter.name}" but parent directory is "${expected}"`);
    }
  });

  // description validation
  check('"description" is valid', () => {
    const desc = frontmatter.description;
    if (typeof desc !== "string" || desc.length === 0) {
      throw new Error('"description" must be a non-empty string');
    }
    if (desc.length > 1024) {
      throw new Error(`"description" must be at most 1024 characters, got ${desc.length}`);
    }
  });

  // allowed-tools validation (optional)
  if ("allowed-tools" in frontmatter) {
    check('"allowed-tools" is a non-empty string', () => {
      const v = frontmatter["allowed-tools"];
      if (typeof v !== "string" || v.length === 0) {
        throw new Error('"allowed-tools" must be a non-empty string if present');
      }
    });
  }

  // license validation (required)
  check('"license" is present and valid', () => {
    if (!("license" in frontmatter)) {
      throw new Error('"license" field is required');
    }
    if (typeof frontmatter.license !== "string" || frontmatter.license.length === 0) {
      throw new Error('"license" must be a non-empty string');
    }
  });

  // compatibility validation (required)
  check('"compatibility" is present and valid', () => {
    if (!("compatibility" in frontmatter)) {
      throw new Error('"compatibility" field is required');
    }
    const v = frontmatter.compatibility;
    if (typeof v !== "string" || v.length === 0) {
      throw new Error('"compatibility" must be a non-empty string');
    }
    if (v.length > 500) {
      throw new Error(`"compatibility" must be at most 500 characters, got ${v.length}`);
    }
  });

  // metadata validation (required)
  check('"metadata" is present and valid', () => {
    if (!("metadata" in frontmatter)) {
      throw new Error('"metadata" field is required');
    }
    const m = frontmatter.metadata;
    if (typeof m !== "object" || m === null || Array.isArray(m)) {
      throw new Error('"metadata" must be a map of key-value pairs');
    }
    for (const [k, v] of Object.entries(m)) {
      if (typeof v !== "string") {
        throw new Error(`metadata key "${k}" must have a string value, got ${typeof v}`);
      }
    }
  });

  // path reference validation
  validatePaths(skillMdPath, content);
}

const skillMdPath = process.argv[2];
if (!skillMdPath) {
  console.error("Usage: node validate-skill.mjs <path-to-SKILL.md>");
  process.exit(1);
}

run(skillMdPath);

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
