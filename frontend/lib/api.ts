// Typed endpoint wrappers. One function per backend route. Components never call apiFetch directly.

import { apiFetch } from "./apiClient";
import type {
  ApproveResult,
  Associate,
  AuditView,
  Case,
  Cockpit,
  CorpusDoc,
  DebriefDoc,
  Decision,
  InboxItem,
  PlanResponse,
  Severity,
  Task,
  TaskDetail,
} from "./types";

// --- Corpus & registry ---
export const getCorpus = () => apiFetch<CorpusDoc[]>("/corpus");
export const getCorpusDoc = (id: string) => apiFetch<CorpusDoc>(`/corpus/${id}`);
export const getAssociates = () => apiFetch<Associate[]>("/associates");

// --- Cases ---
export const listCases = () => apiFetch<Case[]>("/cases");
export const getCase = (id: string) => apiFetch<Case>(`/cases/${id}`);
export const createCase = (body: {
  title: string;
  brief_text: string;
  goal: string;
  severity: Severity;
}) => apiFetch<Case>("/cases", { method: "POST", body: JSON.stringify(body) });

// Bulk-attach documents (PDF / text / DOCX) for the planner to consider. Multipart, not JSON.
export type UploadedDoc = { id: string; title: string };
export const uploadCaseDocuments = (caseId: string, files: File[]) => {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  return apiFetch<UploadedDoc[]>(`/cases/${caseId}/documents`, { method: "POST", body: form });
};

// --- Plan ---
export const createPlan = (caseId: string) =>
  apiFetch<PlanResponse>(`/cases/${caseId}/plan`, { method: "POST" });
export const getPlan = (caseId: string) => apiFetch<PlanResponse>(`/cases/${caseId}/plan`);
export const revisePlan = (caseId: string, feedback: string) =>
  apiFetch<PlanResponse>(`/cases/${caseId}/plan/revise`, {
    method: "POST",
    body: JSON.stringify({ feedback }),
  });

export type TaskPatchBody = Partial<{
  title: string;
  description: string;
  assignee_type: Task["assignee_type"];
  assignee_id: string | null;
  severity: Task["severity"];
  ai_instruction: string;
  human_instruction: string;
  order_index: number;
}>;
export const patchTask = (taskId: string, body: TaskPatchBody) =>
  apiFetch<Task>(`/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify(body) });
export const addPlanTask = (caseId: string) =>
  apiFetch<Task>(`/cases/${caseId}/plan/tasks`, { method: "POST" });
export const deleteTask = (taskId: string) =>
  apiFetch<void>(`/tasks/${taskId}`, { method: "DELETE" });

export const approvePlan = (planId: string) =>
  apiFetch<ApproveResult>(`/plans/${planId}/approve`, { method: "POST" });

// --- Inbox / associate ---
export const getInbox = () => apiFetch<InboxItem[]>("/inbox");
export const submitTask = (taskId: string, body: { summary: string; findings: unknown[] }) =>
  apiFetch<unknown>(`/tasks/${taskId}/submit`, { method: "POST", body: JSON.stringify(body) });

// --- Cockpit / supervision ---
export const getCockpit = (caseId: string) => apiFetch<Cockpit>(`/cases/${caseId}/cockpit`);
export const getTaskDetail = (taskId: string) => apiFetch<TaskDetail>(`/tasks/${taskId}`);

export const decideTask = (
  taskId: string,
  body: { action: "approve" | "amend" | "reject"; note: string; amendment?: string }
) => apiFetch<Decision>(`/tasks/${taskId}/decision`, { method: "POST", body: JSON.stringify(body) });

export const reassignTask = (
  taskId: string,
  body: { assignee_type: Task["assignee_type"]; assignee_id?: string; note: string }
) => apiFetch<unknown>(`/tasks/${taskId}/reassign`, { method: "POST", body: JSON.stringify(body) });

// Partner<->associate ping-pong. Associate body raises a question; partner body answers it.
export const postMessage = (taskId: string, body: { body: string }) =>
  apiFetch<unknown>(`/tasks/${taskId}/message`, { method: "POST", body: JSON.stringify(body) });

// --- Audit & debrief ---
export const getAudit = (caseId: string) => apiFetch<AuditView>(`/cases/${caseId}/audit`);
export const closeCase = (caseId: string) =>
  apiFetch<DebriefDoc>(`/cases/${caseId}/close`, { method: "POST" });
export const getDebrief = (caseId: string) => apiFetch<DebriefDoc>(`/cases/${caseId}/debrief`);
