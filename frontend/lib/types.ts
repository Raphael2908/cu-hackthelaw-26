// Types mirror the FROZEN FastAPI contract exactly. See architecture.md / API contract.

export type CaseStatus = "open" | "closed";
export type Severity = "low" | "medium" | "high" | "extreme";
export type AssigneeType = "human" | "ai" | "hybrid";
export type TaskStatus =
  | "proposed"
  | "approved"
  | "dispatched"
  | "in_progress"
  | "submitted"
  | "checked"
  | "in_review"
  | "signed_off"
  | "escalated"
  | "cleared";

export type SignalType =
  | "citation_support"
  | "precedent_deviation"
  | "multi_run_disagreement";

export type CorpusKind =
  | "legislation"
  | "case_law"
  | "firm_standard"
  | "process_doc"
  | "draft";

export interface Case {
  id: string;
  title: string;
  brief_text: string;
  goal: string;
  severity: Severity;
  process_doc_id: string;
  firm_standard_id: string;
  status: CaseStatus;
  created_by: string;
  created_at: string;
  closed_at?: string;
}

export interface Associate {
  id: string;
  name: string;
  practice_area: string;
  current_load: number;
  capacity: number;
}

export interface CorpusDoc {
  id: string;
  celex: string | null;
  kind: CorpusKind;
  title: string;
  source_url: string;
  text: string;
  clauses?: Record<string, string>;
  ground_truth?: Record<string, unknown>;
  planted_defects?: unknown[];
  created_at?: string;
}

export interface Task {
  id: string;
  case_id: string;
  plan_id: string;
  title: string;
  description: string;
  task_type: string;
  assignee_type: AssigneeType;
  assignee_id: string | null;
  // Why the planner proposed this assignee: task nature + the process map's track record (§6).
  assignee_rationale?: string | null;
  severity: Severity;
  target_document_id: string;
  firm_standard_id: string;
  input_brief_slice: string;
  input_process_section: string;
  ai_instruction: string | null;
  status: TaskStatus;
  order_index: number;
}

export interface Risk {
  task_id: string;
  severity_label: Severity;
  citation_support_rate: number;
  deviation_score: number;
  disagreement_score: number;
  uncertainty: number;
  priority: number;
  lane: "review" | "auto_clear";
  sampled: boolean;
  has_hard_flag: boolean;
}

export interface FlagSourceRef {
  corpus_document_id?: string;
  celex?: string;
  exists?: boolean;
  clause_ref?: string;
  standard_key?: string;
  task_id?: string;
}

export interface Flag {
  id: string;
  task_id: string;
  submission_id: string;
  signal_type: SignalType;
  hard: boolean;
  title: string;
  description: string;
  evidence: Record<string, unknown>;
  source_ref: FlagSourceRef;
}

export interface Finding {
  id: string;
  clause_ref: string;
  statement: string;
  citation: { celex: string; claim: string } | null;
}

export interface Submission {
  id: string;
  task_id: string;
  produced_by: AssigneeType;
  summary: string;
  findings: Finding[];
  citations: { celex: string; claim: string }[];
  clauses_relied_on: string[];
  audit_sources: string[];
  run_index?: number;
}

export interface Card {
  task: Task;
  risk: Risk | null;
  top_flag: Flag | null;
  flag_count: number;
}

export interface Plan {
  id: string;
  case_id: string;
  status: "proposed" | "approved";
  approved_by: string | null;
  approved_at: string | null;
}

export interface PlanResponse {
  plan: Plan;
  tasks: Task[];
}

export interface Cockpit {
  queue: Card[];
  auto_clear_lane: Card[];
  sampled_into_queue: Card[];
  decided: Card[];
  escalated: Card[];
  awaiting_human: Card[];
}

export interface TaskDetail {
  task: Task;
  submission: Submission | null;
  flags: Flag[];
  risk: Risk | null;
}

export interface InboxItem {
  task: Task;
  target_document: CorpusDoc;
  ai_first_pass: Submission | null;
}

export interface AuditEvent {
  id: string;
  kind: "accountability" | "supervision";
  type: string;
  actor: string;
  case_id: string;
  task_id: string | null;
  payload: Record<string, unknown>;
  prev_hash: string;
  hash: string;
  created_at: string;
  seq: number;
}

export interface AuditView {
  accountability: AuditEvent[];
  supervision: AuditEvent[];
  chain_valid: boolean;
}

export interface Decision {
  id: string;
  task_id: string;
  action: "approve" | "amend" | "reject";
  note: string;
  amendment: string | null;
  decided_by: string;
  decided_at: string;
}

export interface ApproveResult {
  plan: Plan;
  dispatched: number;
}

export interface DebriefDoc {
  case_id: string;
  content: string;
  id?: string;
  created_at?: string;
}

// --- Process maps + agentic track record (architecture.md §6) ---

export interface ProcessMapSection {
  label: string;
  severity: Severity;
}

export interface ProcessMap {
  id: string;
  title: string;
  task_types: Record<string, ProcessMapSection>;
}

export interface TrackRecordSection {
  label: string;
  completed: number;
  ai: number;
  hybrid: number;
  clean_successes: number;
  amended: number;
  escalated: number;
  adverse: number;
  clean: boolean;
}

export interface TrackRecordLogItem {
  task_id: string;
  case_id: string;
  task_type: string;
  title: string;
  assignee_type: AssigneeType;
  status: TaskStatus;
  outcome: "clean" | "adverse";
  seq: number;
}

export interface TrackRecord {
  process_doc_id: string;
  by_section: Record<string, TrackRecordSection>;
  log: TrackRecordLogItem[];
}
