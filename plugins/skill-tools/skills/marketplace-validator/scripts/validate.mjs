import { readFileSync, existsSync, readdirSync } from "fs";
import { join, resolve, basename } from "path";

function parseFrontmatter(content) {
  const match = content.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return null;

  const data = {};
  for (const line of match[1].split("\n")) {
    const colon = line.indexOf(":");
    if (colon === -1) continue;
    const key = line.slice(0, colon).trim();
    const value = line.slice(colon + 1).trim();
    if (value === "true") data[key] = true;
    else if (value === "false") data[key] = false;
    else data[key] = value;
  }
  return data;
}

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf-8"));
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

function validateRequired(obj, fields, label) {
  const missing = fields.filter((f) => !(f in obj));
  if (missing.length > 0) {
    throw new Error(`${label} missing required fields: ${missing.join(", ")}`);
  }
}

function validateSkill(skillDir, pluginName) {
  const skillName = basename(skillDir);
  const skillMdPath = join(skillDir, "SKILL.md");

  check(`skill "${pluginName}/${skillName}" — SKILL.md exists`, () => {
    if (!existsSync(skillMdPath)) {
      throw new Error(`Not found: ${skillMdPath}`);
    }
  });

  if (!existsSync(skillMdPath)) return;

  check(`skill "${pluginName}/${skillName}" — frontmatter is valid`, () => {
    const content = readFileSync(skillMdPath, "utf-8");
    const frontmatter = parseFrontmatter(content);

    if (!frontmatter) {
      throw new Error("No YAML frontmatter found");
    }

    validateRequired(
      frontmatter,
      ["name", "description"],
      `${skillName}/SKILL.md frontmatter`
    );
  });
}

function validateClaudePlugin(plugin, repoRoot) {
  const pluginDir = resolve(repoRoot, plugin.source);
  const pluginJsonPath = join(pluginDir, ".claude-plugin", "plugin.json");
  const skillsDir = join(pluginDir, "skills");

  check(`[claude] plugin "${plugin.name}" — has required fields`, () => {
    validateRequired(plugin, ["name", "source", "description"], `plugin "${plugin.name}"`);
  });

  check(`[claude] plugin "${plugin.name}" — source directory exists`, () => {
    if (!existsSync(pluginDir)) {
      throw new Error(`Not found: ${pluginDir}`);
    }
  });

  check(`[claude] plugin "${plugin.name}" — .claude-plugin/plugin.json exists and is valid`, () => {
    if (!existsSync(pluginJsonPath)) {
      throw new Error(`Not found: ${pluginJsonPath}`);
    }
    const pluginJson = readJson(pluginJsonPath);
    validateRequired(pluginJson, ["name", "description", "version"], "plugin.json");
    if (pluginJson.name !== plugin.name) {
      throw new Error(
        `plugin.json name "${pluginJson.name}" does not match marketplace entry "${plugin.name}"`
      );
    }
  });

  check(`[claude] plugin "${plugin.name}" — has skills directory`, () => {
    if (!existsSync(skillsDir)) {
      throw new Error(`Not found: ${skillsDir}`);
    }
  });

  if (!existsSync(skillsDir)) return;

  const skills = readdirSync(skillsDir, { withFileTypes: true }).filter(
    (d) => d.isDirectory()
  );

  check(`[claude] plugin "${plugin.name}" — has at least one skill`, () => {
    if (skills.length === 0) {
      throw new Error(`No skill directories found in ${skillsDir}`);
    }
  });

  for (const skill of skills) {
    validateSkill(join(skillsDir, skill.name), plugin.name);
  }
}

function validateCodexPlugin(plugin, repoRoot) {
  if (!plugin.source || plugin.source.source !== "local" || !plugin.source.path) {
    check(`[codex] plugin "${plugin.name}" — source is local with path`, () => {
      throw new Error(
        `Codex plugin "${plugin.name}" must have source.source = "local" and a source.path`
      );
    });
    return;
  }

  const pluginDir = resolve(repoRoot, plugin.source.path);
  const pluginJsonPath = join(pluginDir, ".codex-plugin", "plugin.json");

  check(`[codex] plugin "${plugin.name}" — has required fields`, () => {
    validateRequired(plugin, ["name", "source", "policy"], `plugin "${plugin.name}"`);
    validateRequired(plugin.policy, ["installation"], `plugin "${plugin.name}".policy`);
  });

  check(`[codex] plugin "${plugin.name}" — source directory exists`, () => {
    if (!existsSync(pluginDir)) {
      throw new Error(`Not found: ${pluginDir}`);
    }
  });

  check(`[codex] plugin "${plugin.name}" — .codex-plugin/plugin.json exists and is valid`, () => {
    if (!existsSync(pluginJsonPath)) {
      throw new Error(`Not found: ${pluginJsonPath}`);
    }
    const pluginJson = readJson(pluginJsonPath);
    validateRequired(pluginJson, ["name", "description", "version"], "plugin.json");
    if (pluginJson.name !== plugin.name) {
      throw new Error(
        `plugin.json name "${pluginJson.name}" does not match marketplace entry "${plugin.name}"`
      );
    }
  });
}

function loadMarketplace(path, requiredFields) {
  if (!existsSync(path)) return null;
  const data = readJson(path);
  validateRequired(data, requiredFields, basename(path));
  if (!Array.isArray(data.plugins)) {
    throw new Error(`${path} 'plugins' must be an array`);
  }
  return data;
}

function run(repoRoot) {
  const claudeManifestPath = join(repoRoot, ".claude-plugin", "marketplace.json");
  const codexManifestPath = join(repoRoot, ".agents", "plugins", "marketplace.json");

  let claudeMarketplace = null;
  let codexMarketplace = null;

  check("Claude marketplace.json is valid JSON with required fields", () => {
    if (!existsSync(claudeManifestPath)) {
      throw new Error(`Not found: ${claudeManifestPath}`);
    }
    claudeMarketplace = loadMarketplace(claudeManifestPath, ["name", "plugins"]);
  });

  check("Codex marketplace.json is valid JSON with required fields", () => {
    if (!existsSync(codexManifestPath)) {
      throw new Error(`Not found: ${codexManifestPath}`);
    }
    codexMarketplace = loadMarketplace(codexManifestPath, ["name", "plugins"]);
  });

  if (claudeMarketplace) {
    for (const plugin of claudeMarketplace.plugins) {
      validateClaudePlugin(plugin, repoRoot);
    }
  }

  if (codexMarketplace) {
    for (const plugin of codexMarketplace.plugins) {
      validateCodexPlugin(plugin, repoRoot);
    }
  }

  if (claudeMarketplace && codexMarketplace) {
    check("Claude and Codex marketplaces list the same plugins", () => {
      const claudeNames = new Set(claudeMarketplace.plugins.map((p) => p.name));
      const codexNames = new Set(codexMarketplace.plugins.map((p) => p.name));

      const missingFromCodex = [...claudeNames].filter((n) => !codexNames.has(n));
      const missingFromClaude = [...codexNames].filter((n) => !claudeNames.has(n));

      if (missingFromCodex.length || missingFromClaude.length) {
        const parts = [];
        if (missingFromCodex.length) {
          parts.push(`missing from Codex: ${missingFromCodex.join(", ")}`);
        }
        if (missingFromClaude.length) {
          parts.push(`missing from Claude: ${missingFromClaude.join(", ")}`);
        }
        throw new Error(parts.join("; "));
      }
    });
  }
}

const repoRoot = process.argv[2];
if (!repoRoot) {
  console.error("Usage: node validate.mjs <repo-root>");
  process.exit(1);
}

run(resolve(repoRoot));

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
