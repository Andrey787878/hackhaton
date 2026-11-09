import type { User } from "../api/types";

export const ROLE_LABELS: Record<string, string> = {
  admin: "Администратор",
  organizer: "Организатор",
  participant: "Участник",
  expert: "Эксперт",
  user: "Пользователь",
  guest: "Гость",
};

export function hasRole(user: User | null | undefined, ...slugs: string[]): boolean {
  if (!user) return false;
  return user.roles.some((role) => role.slug === "admin" || slugs.includes(role.slug));
}

export function roleLabel(slug: string): string {
  return ROLE_LABELS[slug] ?? slug;
}

export function displayName(user: { username: string; display_name: string | null }): string {
  return user.display_name?.trim() || user.username;
}
