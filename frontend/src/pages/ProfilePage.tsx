import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { authApi } from "../api/auth";
import { messageOf } from "../api/errors";
import { setTokens } from "../auth/tokenStorage";
import { useAuth } from "../auth/AuthContext";
import { CopyButton, RoleBadge } from "../components/Badges";
import { Alert, ErrorBox, Loader } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { useAsync } from "../hooks/useAsync";
import { formatDate, initials } from "../utils/format";
import { displayName } from "../utils/roles";

export function ProfilePage() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const sessions = useAsync(() => authApi.sessions(), []);
  const [name, setName] = useState(user?.display_name ?? "");
  const [birthday, setBirthday] = useState(user?.birthday ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  if (!user) return <Loader />;

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      setUser(await authApi.updateMe({ display_name: name.trim() || null, birthday: birthday || null }));
      setSaved(true);
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  };

  const logoutAll = async () => {
    if (!window.confirm("Завершить все сессии, включая текущую?")) return;
    try {
      await authApi.logoutAll();
    } finally {
      setTokens(null);
      navigate("/login");
    }
  };

  return (
    <div className="page narrow">
      <div className="card profile-head">
        <span className="avatar xl">{initials(displayName(user))}</span>
        <div className="grow">
          <h1>{displayName(user)}</h1>
          <p className="muted">
            @{user.username} · {user.email}
          </p>
          <div className="row gap wrap">
            {user.roles.map((role) => (
              <RoleBadge key={role.id} slug={role.slug} />
            ))}
          </div>
        </div>
        <div className="id-box">
          <span className="muted small">ID пользователя</span>
          <span className="mono strong">{user.id}</span>
          <CopyButton value={String(user.id)} label="ID" />
        </div>
      </div>
      <p className="muted small">
        ID нужен организатору, чтобы назначить вас экспертом. Роли выдаёт администратор.
      </p>

      <div className="grid two">
        <form className="card form" onSubmit={save}>
          <h3>
            <Icon name="user" /> Профиль
          </h3>
          <label className="field">
            <span>Отображаемое имя</span>
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={128} />
          </label>
          <label className="field">
            <span>Дата рождения</span>
            <input type="date" value={birthday} onChange={(e) => setBirthday(e.target.value)} />
          </label>
          {error && <Alert tone="error">{error}</Alert>}
          {saved && <Alert tone="success">Профиль сохранён.</Alert>}
          <button className="btn btn-primary" disabled={busy}>
            {busy ? "Сохраняем…" : "Сохранить"}
          </button>
        </form>

        <div className="card">
          <h3>
            <Icon name="lock" /> Активные сессии
          </h3>
          <ErrorBox error={sessions.error} onRetry={sessions.reload} />
          {sessions.loading && !sessions.data && <Loader inline />}
          <ul className="sessions">
            {sessions.data?.items.map((session) => (
              <li key={session.id}>
                <Icon name="server" size={16} />
                <div className="grow small">
                  <div className="strong">{session.user_agent?.slice(0, 60) || "Неизвестный клиент"}</div>
                  <div className="muted">
                    {session.ip ?? "—"} · вход {formatDate(session.created_at)}
                  </div>
                </div>
              </li>
            ))}
          </ul>
          <button type="button" className="btn btn-danger btn-sm" onClick={logoutAll}>
            <Icon name="logout" size={14} /> Выйти на всех устройствах
          </button>
        </div>
      </div>
    </div>
  );
}
