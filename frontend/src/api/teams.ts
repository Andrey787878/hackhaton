import { api, download, upload, type UploadProgress } from "./client";
import type { InviteCreated, InviteInfo, Submission, Team } from "./types";

export const teamsApi = {
  mine: () => api.get<Team[]>("/teams", { query: { limit: 100 } }),
  get: (id: number) => api.get<Team>(`/teams/${id}`),
  create: (hackathonId: number, name: string) => api.post<Team>(`/hackathons/${hackathonId}/teams`, { name }),
  rename: (id: number, name: string) => api.patch<Team>(`/teams/${id}`, { name }),
  join: (code: string) => api.post<Team>("/teams/join", { code }),
  invite: (id: number) => api.get<InviteInfo>(`/teams/${id}/invite`),
  issueInvite: (id: number) => api.post<InviteCreated>(`/teams/${id}/invite`),
  revokeInvite: (id: number) => api.delete(`/teams/${id}/invite`),
  byHackathon: (hackathonId: number) =>
    api.get<Team[]>(`/organizer/hackathons/${hackathonId}/teams`, { query: { limit: 100 } }),
};

export const submissionsApi = {
  list: (teamId: number, caseId?: number) =>
    api.get<Submission[]>(`/teams/${teamId}/submissions`, { query: { case_id: caseId, limit: 100 } }),
  get: (id: number) => api.get<Submission>(`/submissions/${id}`),
  submit: (
    teamId: number,
    data: { caseId: number; url?: string; archive?: File | null },
    onProgress?: (progress: UploadProgress) => void,
  ) => {
    const form = new FormData();
    form.set("case_id", String(data.caseId));
    if (data.url) form.set("url", data.url);
    if (data.archive) form.set("archive", data.archive, data.archive.name);
    return upload<Submission>(`/teams/${teamId}/submissions`, form, onProgress);
  },
  downloadArchive: (submission: Submission) =>
    download(`/submissions/${submission.id}/archive`, submission.archive?.filename ?? `submission-${submission.id}`),
};
