import { api } from "./client";
import type { Assignment, ScoreValue } from "./types";

export const expertApi = {
  assignments: () => api.get<Assignment[]>("/expert/assignments", { query: { limit: 100 } }),
  assignment: (id: number) => api.get<Assignment>(`/expert/assignments/${id}`),
  score: (id: number, scores: ScoreValue[]) => api.put<Assignment>(`/expert/assignments/${id}/scores`, { scores }),
};

export const assignmentsApi = {
  list: (hackathonId: number) =>
    api.get<Assignment[]>(`/organizer/hackathons/${hackathonId}/assignments`, { query: { limit: 100 } }),
  assign: (hackathonId: number, data: { team_id: number; case_id: number; expert_id: number }) =>
    api.post<Assignment>(`/organizer/hackathons/${hackathonId}/assignments`, data),
};
