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
  | "returned"
  | "awaiting_clarification"
  | "signed_off"
  | "escalated"
  | "cleared";

export type MessageKind = "return" | "question" | "answer";

export interface TaskMessage {
  id: string;
  task_id: string;
  case_id: string;
  author_role: "partner" | "associate";
  author: string;
  kind: MessageKind;
  body: string;
  created_at: string;
}

export type SignalType =
  | "citation_support"
  | "precedent_deviation"
  | "multi_run_disagreement";

// The kind of work the flexible worker executes for a task (architecture.md §6). Drives the
// per-task-type output `payload` carried on the submission.
export type TaskKind = "review" | "summarize" | "extract" | "draft";

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
  instructions?: string;
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
  human_instruction: string | null; // the associate's half of a hybrid task
  rationale: string | null; // one-line planner reasoning, for the partner to verify
  status: TaskStatus;
  order_index: number;
  // When the coordinator dispatched this AI/hybrid task — server-authoritative, so the cockpit's
  // "With AI" lane can show a live elapsed timer that doesn't reset on poll. Absent until dispatch.
  run_started_at?: string | null;
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
  // Which signals actually ran for this task. A signal marked false is "not applicable" and was
  // excluded from the uncertainty composite — shown as n/a, never a misleading 0.0 (§7.2/§14.4).
  // Absent on older records → treat all as applied.
  applied_checks?: Partial<Record<SignalType, boolean>>;
}

export interface FlagSourceRef {
  corpus_document_id?: string;
  celex?: string;
  exists?: boolean;
  clause_ref?: string;
  standard_key?: string;
  task_id?: string;
}

// The quoting side of a flag — the passage in the SUBMITTED WORK that cited the source / deviated.
export interface FlagWorkRef {
  clause_ref?: string | null;
  statement?: string; // what the output asserted / the draft's own clause text
  claim?: string | null; // citation only: the proposition the work attributed to the source
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
  work_ref?: FlagWorkRef;
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
  // The flexible worker's type-specific product. `output_kind` discriminates the `payload` shape
  // (e.g. extract → {obligations}, summarize → {key_points}, draft → {draft_text}). `review` carries
  // no payload — its product is the findings (architecture.md §6).
  output_kind?: TaskKind;
  payload?: Record<string, unknown>;
  run_index?: number;
}

export interface Card {
  task: Task;
  risk: Risk | null;
  top_flag: Flag | null;
  flag_count: number;
  messages?: TaskMessage[]; // attached for needs_reply cards (the open question thread)
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

export interface PendingSummary {
  total: number;
  awaiting_decision: number; // submitted / checked / in_review — awaiting the partner's decision
  with_associate: number; // dispatched / in_progress / returned / awaiting_clarification
  not_run: number; // proposed / approved — planned but not yet started
}

export interface Cockpit {
  queue: Card[];
  auto_clear_lane: Card[];
  sampled_into_queue: Card[];
  decided: Card[];
  escalated: Card[];
  with_ai: Card[]; // AI/hybrid tasks running the worker→checker→ranker pipeline right now
  awaiting_human: Card[];
  needs_reply: Card[];
  pending: PendingSummary;
}

export interface Attachment {
  id: string; // corpus document id — openable in the source drawer
  title: string;
}
export interface TaskDetail {
  task: Task;
  submission: Submission | null;
  flags: Flag[];
  risk: Risk | null;
  messages: TaskMessage[];
  attachments: Attachment[];
}

export interface InboxItem {
  task: Task;
  target_document: CorpusDoc;
  ai_first_pass: Submission | null;
  last_submission: Submission | null;
  messages: TaskMessage[];
  attachments: Attachment[];
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

// The debrief is an issue-centric structured payload composed server-side (no markdown parsing).
export interface DebriefFlag {
  signal_type: SignalType;
  hard: boolean;
  title: string;
  description: string;
  source_ref?: FlagSourceRef;
  work_ref?: FlagWorkRef;
}
export interface DebriefDecision {
  action: "approve" | "amend" | "reject";
  note: string;
  amendment?: string | null;
}
export interface DebriefIssue {
  task_title: string;
  severity: Severity;
  status: TaskStatus;
  assignee_type: AssigneeType;
  flags: DebriefFlag[];
  decision: DebriefDecision | null;
}
export interface DebriefContent {
  case_title: string;
  goal: string;
  summary: {
    tasks: number;
    needs_attention: number;
    cleared: number;
    hard_flags: number;
    rejected: number;
    carry_forward: number;
  };
  issues: DebriefIssue[];
  cleared: { task_title: string; severity: Severity; status: TaskStatus }[];
  carry_forward: string[];
}
export interface DebriefDoc {
  case_id: string;
  content: DebriefContent;
  id?: string;
  created_at?: string;
}

// --- Process maps + agentic track record (architecture.md §6) ---

export interface ProcessMapSection {
  label: string;
  severity: Severity;
  // The partner-authored worker spec for this section (architecture.md §6). Optional — a section
  // that omits them behaves like the original review task.
  kind?: TaskKind;
  instruction?: string | null;
  checklist?: string[];
  checks?: SignalType[];
  requires_standard?: boolean;
}

export interface ProcessMap {
  id: string;
  title: string;
  task_types: Record<string, ProcessMapSection>;
}

export interface TrackRecordLesson {
  case_id: string;
  case_title: string;
  action: "amend" | "reject";
  text: string; // the partner's own amendment / rejection words
}
export interface TrackRecordSectionCase {
  case_id: string;
  title: string;
  status: CaseStatus;
  completed: number;
  adverse: number;
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
  // Feedback detail (per section): flags by checker signal (hard/soft), the partner's carry-forward
  // notes, and the matters the section ran in. Counts + recorded words + flags, never a verdict.
  flags_by_signal: Record<SignalType, { count: number; hard: number }>;
  hard_flags: number;
  lessons: TrackRecordLesson[];
  cases: TrackRecordSectionCase[];
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
