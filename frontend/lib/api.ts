import { apiFetch } from "./apiClient";
import type { Candidate, Output, Task } from "./types";

export interface CreateTaskInput {
  title: string;
  brief: string;
  task_type?: string;
  eval_doc_count?: number;
}

export const api = {
  listTasks: () => apiFetch<Task[]>("/tasks"),
  getTask: (id: string) => apiFetch<Task>(`/tasks/${id}`),
  createTask: (input: CreateTaskInput) =>
    apiFetch<Task>("/tasks", { method: "POST", body: JSON.stringify(input) }),
  listCandidates: (id: string) => apiFetch<Candidate[]>(`/tasks/${id}/candidates`),
  getOutput: (id: string) => apiFetch<Output>(`/tasks/${id}/output`),
};
