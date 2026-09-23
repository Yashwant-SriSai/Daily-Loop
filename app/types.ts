export type lead = {
    topic: string;
    headline: string;
    source_count: number;
    body: string[];
};
export type Brief = {
  category: string;
  source_count: number;
  headline: string;
  body: string;
};
export type ResearchPaper = {
  title: string;
  authors: string;
  summary: string;
  link: string;
};
export type Explainli5={
    title:string;
    explaination:string;
};
export type DsaProblem={
    title: string;
    difficulty: string;
    function_name: string;
    python_solution: string;
    explanation: string;

    prompt: string;
    test_cases:{args: unknown[]; expected: unknown}[];
};

export type Dsa={
    basic:DsaProblem;
    advanced:DsaProblem;
};


export type Edition = {
  lead: lead;
  briefs: Brief[];
  explainli5: Explainli5[];
  paper: ResearchPaper[];
  dsa:Dsa;
};