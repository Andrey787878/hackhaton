import { api } from "./client";
import type {
  Case,
  CriterionInput,
  Hackathon,
  HackathonInput,
  HackathonResults,
  HackathonStatus,
  Health,
  Leaderboard,
} from "./types";

/** Публичная часть: доступна наблюдателю без входа. */
export const publicApi = {
  health: () => api.get<Health>("/health", { auth: false }),
  time: () => api.get<{ server_time: string }>("/time", { auth: false }),
  hackathons: (limit = 50, offset = 0) =>
    api.get<Hackathon[]>("/hackathons", { auth: false, query: { limit, offset } }),
  hackathon: (id: number) => api.get<HackathonStatus>(`/hackathons/${id}`, { auth: false }),
  cases: (id: number) => api.get<Case[]>(`/hackathons/${id}/cases`, { auth: false }),
  leaderboard: (hackathonId: number, caseId: number) =>
    api.get<Leaderboard>(`/hackathons/${hackathonId}/cases/${caseId}/leaderboard`, { auth: false }),
  /** Итоги всех кейсов после дедлайна (публичный список кейсов к этому моменту закрыт). */
  results: (hackathonId: number) =>
    api.get<HackathonResults>(`/hackathons/${hackathonId}/leaderboard`, { auth: false }),
};

/** Кабинет организатора: только свои мероприятия (проверяет сервер). */
export const organizerApi = {
  list: (limit = 100, offset = 0) =>
    api.get<Hackathon[]>("/organizer/hackathons", { query: { limit, offset } }),
  get: (id: number) => api.get<Hackathon>(`/organizer/hackathons/${id}`),
  create: (data: HackathonInput) => api.post<Hackathon>("/organizer/hackathons", data),
  update: (id: number, data: HackathonInput) => api.put<Hackathon>(`/organizer/hackathons/${id}`, data),
  publish: (id: number) => api.post<Hackathon>(`/organizer/hackathons/${id}/publish`),
  unpublish: (id: number) => api.post<Hackathon>(`/organizer/hackathons/${id}/unpublish`),
  cases: (id: number) => api.get<Case[]>(`/organizer/hackathons/${id}/cases`),
  createCase: (id: number, data: { title: string; description: string }) =>
    api.post<Case>(`/organizer/hackathons/${id}/cases`, data),
  updateCase: (id: number, caseId: number, data: { title: string; description: string }) =>
    api.put<Case>(`/organizer/hackathons/${id}/cases/${caseId}`, data),
  setCriteria: (id: number, caseId: number, criteria: CriterionInput[]) =>
    api.put<Case>(`/organizer/hackathons/${id}/cases/${caseId}/criteria`, { criteria }),
  removeCase: (id: number, caseId: number) => api.delete(`/organizer/hackathons/${id}/cases/${caseId}`),
};
