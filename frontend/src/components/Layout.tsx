import { useCallback, useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { publicApi } from "../api/hackathons";
import { notificationsApi } from "../api/notifications";
import { useAuth } from "../auth/AuthContext";
import { useInterval } from "../hooks/useInterval";
import { useServerNow } from "../hooks/useServerNow";
import { initials } from "../utils/format";
import { displayName, hasRole } from "../utils/roles";
import { Icon } from "./Icon";

export const NOTIFICATIONS_CHANGED = "hackpulse:notifications-changed";

function useUnreadCount(enabled: boolean) {
  const [count, setCount] = useState(0);
  const load = useCallback(() => {
    if (!enabled) return;
    notificationsApi
      .unreadCount()
      .then((data) => setCount(data.count))
      .catch(() => undefined);
  }, [enabled]);
  useEffect(() => {
    if (!enabled) {
      setCount(0);
      return;
    }
    load();
    window.addEventListener(NOTIFICATIONS_CHANGED, load);
    return () => window.removeEventListener(NOTIFICATIONS_CHANGED, load);
  }, [enabled, load]);
  useInterval(load, enabled ? 30000 : null);
  return count;
}

function ApiStatus() {
  const [ok, setOk] = useState<boolean | null>(null);
  const check = useCallback(() => {
    publicApi
      .health()
      .then((data) => setOk(data.status === "ok" && data.database === "ok"))
      .catch(() => setOk(false));
  }, []);
  useEffect(check, [check]);
  useInterval(check, 30000);
  const now = useServerNow();
  return (
    <div className="api-status">
      <span className={`status-dot ${ok === null ? "" : ok ? "ok" : "down"}`} aria-hidden />
      {ok === null ? "Проверяем API…" : ok ? "API и база данных доступны" : "API недоступен"}
      <span className="sep">·</span>
      <span className="mono">{new Date(now).toISOString().slice(11, 19)} UTC</span>
    </div>
  );
}

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const unread = useUnreadCount(Boolean(user));

  useEffect(() => setMenuOpen(false), [location.pathname]);

  const onLogout = async () => {
    await logout();
    navigate("/");
  };

  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="brand" aria-label="HackPulse — на главную">
            <span className="brand-mark">
              <Icon name="bolt" size={18} />
            </span>
            <span className="brand-name">
              Hack<span>Pulse</span>
            </span>
          </Link>

          <button
            type="button"
            className="btn btn-icon burger"
            aria-label="Меню"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
          >
            <Icon name={menuOpen ? "x" : "menu"} />
          </button>

          <nav className={menuOpen ? "nav open" : "nav"} aria-label="Основная навигация">
            <NavLink to="/" end>
              <Icon name="layers" size={16} /> Хакатоны
            </NavLink>
            {hasRole(user, "participant") && (
              <NavLink to="/teams">
                <Icon name="users" size={16} /> Мои команды
              </NavLink>
            )}
            {hasRole(user, "expert") && (
              <NavLink to="/expert">
                <Icon name="star" size={16} /> Экспертиза
              </NavLink>
            )}
            {hasRole(user, "organizer") && (
              <NavLink to="/organizer">
                <Icon name="shield" size={16} /> Организатор
              </NavLink>
            )}

            <div className="nav-spacer" />

            {user ? (
              <>
                <NavLink to="/notifications" className="nav-bell" aria-label={`Уведомления: ${unread} новых`}>
                  <Icon name="bell" size={16} />
                  <span className="hide-desktop">Уведомления</span>
                  {unread > 0 && <span className="counter">{unread > 99 ? "99+" : unread}</span>}
                </NavLink>
                <NavLink to="/profile" className="nav-user">
                  <span className="avatar">{initials(displayName(user))}</span>
                  <span className="nav-user-name">{displayName(user)}</span>
                </NavLink>
                <button type="button" className="btn btn-sm btn-ghost" onClick={onLogout}>
                  <Icon name="logout" size={14} /> Выйти
                </button>
              </>
            ) : (
              <>
                <NavLink to="/login">Войти</NavLink>
                <Link to="/register" className="btn btn-sm btn-primary">
                  Регистрация
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      <main className="content">
        <Outlet />
      </main>

      <footer className="footer">
        <div className="footer-inner">
          <span>HackPulse · платформа онлайн-хакатонов</span>
          <ApiStatus />
        </div>
      </footer>
    </div>
  );
}
