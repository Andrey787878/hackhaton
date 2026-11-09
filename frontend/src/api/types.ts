// Типы ответов FastAPI (см. app/*_schemas.py и app/dto.py бэкенда).
// Даты приходят строками ISO 8601 в UTC, Decimal — строками.

export type RoleSlug = "admin" | "organizer" | "participant" | "expert" | string;

export interface Role {
  id: number;
  name: string;
  slug: RoleSlug;
  description: string | null;
}

export interface User {
  id: number;
  username: string;
  email: string;
  birthday: string | null;
  display_name: string | null;
  roles: Role[];
}

export interface AuthSuccess {
  access_token: string;
  refresh_token: string;
  user: User;
}

export interface SessionMeta {
  id: number;
  created_at: string;
  last_used_at: string | null;
  access_expires_at: string;
  refresh_expires_at?: string;
  ip?: string | null;
  user_agent?: string | null;
}

export interface Criterion {
  id: number;
  position: number;
  title: string;
  description: string;
  min_score: number;
  max_score: number;
  weight: string;
}

export interface CriterionInput {
  title: string;
  description: string;
  min_score: number;
  max_score: number;
  weight: string;
}

export interface Case {
  id: number;
  hackathon_id: number;
  title: string;
  description: string;
  criteria: Criterion[];
}

export interface Hackathon {
  id: number;
  organizer_id: number;
  title: string;
  description: string;
  starts_at: string;
  deadline_at: string;
  is_published: boolean;
}

export interface HackathonInput {
  title: string;
  description: string;
  starts_at: string;
  deadline_at: string;
}

export type Phase = "upcoming" | "active" | "finished";

export interface HackathonStatus {
  hackathon: Hackathon;
  server_time: string;
  phase: Phase;
  materials_available: boolean;
}

export interface Member {
  user_id: number;
  username: string;
  display_name: string | null;
  joined_at: string;
}

export interface Team {
  id: number;
  hackathon_id: number;
  captain_id: number;
  name: string;
  created_at: string;
  members: Member[];
}

export interface InviteInfo {
  team_id: number;
  active: boolean;
  created_at: string | null;
  expires_at: string;
}

export interface InviteCreated extends InviteInfo {
  code: string;
}

export interface ArchiveInfo {
  filename: string;
  size_bytes: number;
  sha256: string;
}

export interface Submission {
  id: number;
  team_id: number;
  case_id: number;
  submitted_by: number;
  submitted_at: string;
  url: string | null;
  archive: ArchiveInfo | null;
}

export interface ScoreValue {
  criterion_id: number;
  value: number;
}

export interface Assignment {
  id: number;
  expert_id: number;
  assigned_at: string;
  submission: Submission;
  criteria: Criterion[];
  scores: ScoreValue[];
  complete: boolean;
  total: string | null;
}

export interface LeaderboardEntry {
  rank: number;
  team_id: number;
  team_name: string;
  case_id: number;
  total: string;
  expert_count: number;
}

export interface Leaderboard {
  hackathon_id: number;
  case_id: number;
  entries: LeaderboardEntry[];
}

export interface CaseLeaderboard extends Leaderboard {
  title: string;
}

export interface HackathonResults {
  hackathon_id: number;
  cases: CaseLeaderboard[];
}

export type NotificationKind =
  | "hackathon_published"
  | "team_joined"
  | "submission_created"
  | "expert_assigned"
  | "score_completed";

export interface AppNotification {
  id: number;
  kind: NotificationKind;
  title: string;
  actor_id: number;
  resource_type: "hackathon" | "team" | "submission" | "assignment";
  resource_id: number;
  created_at: string;
  read_at: string | null;
}

export interface Health {
  status: string;
  database: string;
}
