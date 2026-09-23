"use client";
import type { Dsa } from "./types";

import { useState } from "react";

export function DsaReveal({ approach }: { approach: string }) {
  const [show, setShow] = useState(false);

  return (
    <>
      <button onClick={() => setShow(!show)}>
        {show ? "Hide approach" : "Reveal approach"}
      </button>
      {show && <p>{approach}</p>}
    </>
  );
}
export function DsaSection({ dsa }: { dsa: Dsa }) {
  const [level, setLevel] = useState<"basic" | "advanced">("basic");
  const problem = dsa[level];

  return (
    <div>
      <div className="dsa-toggle">
        <button
          className={level === "basic" ? "active" : ""}
          onClick={() => setLevel("basic")}
        >
          Basic
        </button>
        <button
          className={level === "advanced" ? "active" : ""}
          onClick={() => setLevel("advanced")}
        >
          Advanced
        </button>
      </div>
      <p className="dsa-difficulty">{problem.difficulty}</p>
      <p>{problem.title}</p>
      <p>{problem.prompt}</p>
      <DsaReveal approach={problem.explanation} />
      <pre className="code-block"><code>{problem.python_solution}</code></pre>
    </div>
  );
}