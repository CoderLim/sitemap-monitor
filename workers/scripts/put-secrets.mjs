#!/usr/bin/env node
/**
 * Put Cloudflare Worker secrets from env (or sibling link-master/.env.local).
 *
 * Usage:
 *   npm run secrets
 *   GITHUB_TOKEN=... ACCESS_PASSWORD=... npm run secrets
 */
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const siblingEnv = resolve(root, "../link-master/.env.local");

function parseDotenv(path) {
  if (!existsSync(path)) return {};
  const out = {};
  for (const raw of readFileSync(path, "utf8").split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const i = line.indexOf("=");
    const key = line.slice(0, i).trim();
    let value = line.slice(i + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (key) out[key] = value;
  }
  return out;
}

const fromFile = parseDotenv(siblingEnv);
const githubToken = process.env.GITHUB_TOKEN || fromFile.GITHUB_TOKEN || "";
const accessPassword =
  process.env.ACCESS_PASSWORD ||
  process.env.DASHBOARD_TOKEN ||
  fromFile.ACCESS_PASSWORD ||
  fromFile.DASHBOARD_TOKEN ||
  "";

if (!githubToken) {
  console.error(
    "Missing GITHUB_TOKEN. Set env or put it in ../link-master/.env.local",
  );
  process.exit(1);
}
if (!accessPassword) {
  console.error(
    "Missing ACCESS_PASSWORD / DASHBOARD_TOKEN. Set env or put it in ../link-master/.env.local",
  );
  process.exit(1);
}

function putSecret(name, value) {
  console.log(`Putting secret ${name}...`);
  const result = spawnSync("npx", ["wrangler", "secret", "put", name], {
    input: value,
    encoding: "utf8",
    stdio: ["pipe", "inherit", "inherit"],
    cwd: resolve(root, "workers"),
  });
  if (result.status !== 0) {
    process.exit(result.status || 1);
  }
}

putSecret("GITHUB_TOKEN", githubToken);
putSecret("ACCESS_PASSWORD", accessPassword);
console.log("Done.");
