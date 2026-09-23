export type Lead = {
  topic: string;
  headline: string;
  source_count: number;
  paragraphs: string[];
};

export type Brief = {
  category: string;
  source_count: number;
  headline: string;
  body: string;
};

export type Explainli5 = {
  title: string;
  explanation: string;
  deep_dive: string;
};

export type DsaProblem = {
  title: string;
  difficulty: string;
  prompt: string;
  function_name: string;
  python_solution: string;
  explanation: string;
  time_complexity: string;
  space_complexity: string;
  test_cases: { args: unknown[]; expected: unknown }[];
};

export type Dsa = {
  basic: DsaProblem;
  advanced: DsaProblem;
};

export type ResearchPaper = {
  title: string;
  authors: string;
  summary: string;
  link: string;
};

export type Edition = {
  generated_date: string;
  lead: Lead;
  briefs: Brief[];
  explainli5: Explainli5;
  dsa: Dsa;
  paper: ResearchPaper | null;
};