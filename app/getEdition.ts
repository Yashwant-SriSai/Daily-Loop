import { execSync } from "child_process";
import { readFileSync } from "fs";
import path from "path";
import type { Edition } from "./types";

const EDITION_PATH = path.join(process.cwd(), "data", "edition.json");
const RETRY_COOLDOWN_MS = 30 * 60 * 1000; // don't retry a failed run for 30 min

let lastFailedAt = 0;

function readEditionFile(): Edition | null {
  try {
    return JSON.parse(readFileSync(EDITION_PATH, "utf-8"));
  } catch {
    return null;
  }
}

export async function getTodaysEdition(): Promise<Edition> {
  const today = new Date().toISOString().slice(0, 10);
  const existing = readEditionFile();

  if (existing && existing.generated_date === today) return existing;

  // A recent run failed: serve the old edition instead of burning tokens again.
  if (existing && Date.now() - lastFailedAt < RETRY_COOLDOWN_MS) return existing;

  console.log("Edition missing or stale, regenerating via Python...");
  try {
    execSync("python3 scripts/generate_edition.py", {
      cwd: process.cwd(),
      stdio: "inherit",
      timeout: 5 * 60 * 1000,
    });
  } catch (err) {
    console.error("Regeneration failed:", err);
    lastFailedAt = Date.now();
    if (existing) return existing;
    throw err;
  }

  return readEditionFile() ?? existing!;
}