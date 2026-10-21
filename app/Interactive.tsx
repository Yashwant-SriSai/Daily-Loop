"use client";

import { useState, useRef, useEffect } from "react";
import type { Dsa, DsaProblem } from "./types";

export function DsaReveal({ problem }: { problem: DsaProblem }) {
  const [show, setShow] = useState(false);

  return (
    <>
      <button onClick={() => setShow(!show)}>
        {show ? "Hide approach" : "Show approach"}
      </button>
      {show && (
        <div className="dsa-reveal">
          <p>{problem.explanation}</p>
          <p className="dsa-complexity">
            Time: {problem.time_complexity} &nbsp;&middot;&nbsp; Space: {problem.space_complexity}
          </p>
          <pre className="code-block"><code>{problem.python_solution}</code></pre>
        </div>
      )}
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
      <DsaReveal problem={problem} />
    </div>
  );
}
export function BriefCard({
  category, headline, body, icon,
}: { category: string; headline: string; body: string; icon: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [overflows, setOverflows] = useState(false);
  const ref = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (el && !open) setOverflows(el.scrollHeight > el.clientHeight + 1);
  }, [body, open]);

  return (
    <div className="story">
      <div className="tag">{icon} {category}</div>
      <h3>{headline}</h3>
      <p ref={ref} className={`story-body ${open ? "" : "clamped"}`}>{body}</p>
      {(overflows || open) && (
        <button className="read-toggle" onClick={() => setOpen(!open)}>
          {open ? "Read less" : "Read more"}
        </button>
      )}
    </div>
  );
}