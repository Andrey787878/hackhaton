import { useState } from "react";
import { Link } from "react-router-dom";
import { messageOf } from "../api/errors";
import { notificationsApi } from "../api/notifications";
import type { AppNotification, NotificationKind } from "../api/types";
import { Alert, EmptyState, ErrorBox, Loader } from "../components/Feedback";
import { Icon, type IconName } from "../components/Icon";
import { NOTIFICATIONS_CHANGED } from "../components/Layout";
import { useAsync } from "../hooks/useAsync";
import { formatDateSeconds } from "../utils/format";

const KIND: Record<NotificationKind, { icon: IconName; label: string }> = {
  hackathon_published: { icon: "send", label: "Публикация" },
  team_joined: { icon: "users", label: "Команда" },
  submission_created: { icon: "upload", label: "Сдача" },
  expert_assigned: { icon: "star", label: "Назначение" },
  score_completed: { icon: "trophy", label: "Оценка" },
};

function linkFor(item: AppNotification): string | null {
  if (item.resource_type === "hackathon") return `/hackathons/${item.resource_id}`;
  if (item.resource_type === "team") return `/teams/${item.resource_id}`;
  if (item.resource_type === "assignment" && item.kind === "expert_assigned") return `/expert/assignments/${item.resource_id}`;
  return null;
}

export function NotificationsPage() {
  const [unreadOnly, setUnreadOnly] = useState(false);
  const list = useAsync(() => notificationsApi.list(unreadOnly), [unreadOnly]);
  const [error, setError] = useState<string | null>(null);

  const markRead = async (item: AppNotification) => {
    try {
      const updated = await notificationsApi.markRead(item.id);
      list.setData((prev) => (prev ?? []).map((n) => (n.id === item.id ? updated : n)));
      window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED));
    } catch (err) {
      setError(messageOf(err));
    }
  };

  const markAll = async () => {
    const unread = (list.data ?? []).filter((n) => !n.read_at);
    try {
      await Promise.all(unread.map((n) => notificationsApi.markRead(n.id)));
      await list.reload();
      window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED));
    } catch (err) {
      setError(messageOf(err));
    }
  };

  const unreadCount = (list.data ?? []).filter((n) => !n.read_at).length;

  return (
    <div className="page narrow">
      <div className="section-head">
        <div>
          <span className="eyebrow">
            <Icon name="bell" size={14} /> Журнал событий
          </span>
          <h1>Уведомления</h1>
        </div>
        <div className="row gap wrap">
          <label className="switch">
            <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} />
            <span>только новые</span>
          </label>
          {unreadCount > 0 && (
            <button type="button" className="btn btn-sm btn-ghost" onClick={markAll}>
              <Icon name="check" size={14} /> Прочитать все
            </button>
          )}
        </div>
      </div>
      <ErrorBox error={list.error} onRetry={list.reload} />
      {error && <Alert tone="error">{error}</Alert>}
      {list.loading && !list.data && <Loader />}
      {list.data?.length === 0 && (
        <div className="card">
          <EmptyState icon="bell" title={unreadOnly ? "Новых уведомлений нет" : "Уведомлений пока нет"}>
            Здесь появятся публикации, вступления в команду, сдачи решений, назначения и оценки.
          </EmptyState>
        </div>
      )}
      <ul className="notifications">
        {list.data?.map((item) => {
          const kind = KIND[item.kind] ?? { icon: "bell" as IconName, label: item.kind };
          const href = linkFor(item);
          return (
            <li key={item.id} className={item.read_at ? "card notification" : "card notification unread"}>
              <span className={`notification-icon kind-${item.kind}`}>
                <Icon name={kind.icon} />
              </span>
              <div className="grow">
                <div className="row gap wrap">
                  <span className="chip">{kind.label}</span>
                  <span className="muted small">{formatDateSeconds(item.created_at)}</span>
                </div>
                <div className="strong">{href ? <Link to={href}>{item.title}</Link> : item.title}</div>
              </div>
              {!item.read_at && (
                <button type="button" className="btn btn-sm btn-ghost" onClick={() => markRead(item)}>
                  Прочитано
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
