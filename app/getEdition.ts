import { execSync } from "child_process";
import { readFileSync } from "fs";
import path from "path";
import type { Edition } from "./types";

const EDITION_PATH = path.join(process.cwd(), "data", "edition.json");

function readEditionFile(): (Edition & { generated_date: string }) | null {
  try {
    const raw = readFileSync(EDITION_PATH, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export async function getTodaysEdition(): Promise<Edition> {
  const today = new Date().toISOString().slice(0, 10); // "YYYY-MM-DD"
  const existing = readEditionFile();

  if (existing && existing.generated_date === today) {
    console.log("Edition is already fresh for today, skipping regeneration.");
    return existing;
  }

  console.log("Edition missing or stale — regenerating via Python...");
  execSync("python scripts/generate_edition.py", {
    cwd: process.cwd(),
    stdio: "inherit", // shows Python's print() output in your terminal
  });

  const fresh = readEditionFile();
  if (!fresh) throw new Error("Regeneration ran but edition.json is still missing/invalid.");
  return fresh;
}