export type TaskStatus =
  | "planning"
  | "researching"
  | "ranking"
  | "evaluating"
  | "synthesizing"
  | "complete"
  | "failed";

export interface Task {
  id: string;
  user_id: string;
  task_type: string;
  title: string;
  brief: string;
  eval_doc_count: number;
  status: TaskStatus;
  plan_md: string | null;
  created_at: string;
}

export interface Candidate {
  id: string;
  task_id: string;
  origin: "web" | "cellar" | "upload";
  title: string | null;
  url: string | null;
  snippet: string | null;
  rank: number | null;
  relevance_score: number | null;
  evaluated: boolean;
  eval_relevance: number | null;
  eval_risk: number | null;
  eval_uncertainty: number | null;
  eval_notes: string | null;
  use_in_synthesis: boolean;
}

export interface Output {
  id: string;
  task_id: string;
  version: number;
  content_md: string;
  created_at: string;
}
