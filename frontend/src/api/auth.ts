import { api } from "./client";
import type { AuthSuccess, SessionMeta, User } from "./types";

export interface RegisterInput {
  username: string;
  email: string;
  password: string;
  c_password: string;
  birthday?: string | null;
  display_name?: string | null;
}

export interface ProfileInput {
  display_name?: string | null;
  birthday?: string | null;
}

export const authApi = {
  login: (username: string, password: string) =>
    api.post<AuthSuccess>("/auth/login", { username, password }, { auth: false }),
  register: (data: RegisterInput) => api.post<User>("/auth/register", data, { auth: false }),
  me: () => api.get<User>("/auth/me"),
  updateMe: (data: ProfileInput) => api.patch<User>("/auth/me", data),
  sessions: () => api.get<{ items: SessionMeta[] }>("/auth/tokens"),
  logout: () => api.post<{ message: string }>("/auth/out"),
  logoutAll: () => api.post<{ message: string; revoked_count: number }>("/auth/out_all"),
};
