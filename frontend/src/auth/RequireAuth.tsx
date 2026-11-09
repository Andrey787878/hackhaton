import type { ReactNode } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { EmptyState, Loader } from "../components/Feedback";
import { hasRole, roleLabel } from "../utils/roles";
import { useAuth } from "./AuthContext";

/** Защищённый маршрут: без входа — на /login, без роли — понятное сообщение. */
export function RequireAuth({ roles, children }: { roles?: string[]; children: ReactNode }) {
  const { user, initializing } = useAuth();
  const location = useLocation();

  if (initializing) return <Loader label="Восстанавливаем сессию…" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  if (roles && !hasRole(user, ...roles)) {
    return (
      <div className="page narrow">
        <div className="card">
          <EmptyState
            icon="lock"
            title="Нет доступа"
            action={
              <Link className="btn" to="/">
                На главную
              </Link>
            }
          >
            Раздел доступен ролям: {roles.map(roleLabel).join(", ")}. Роли назначает администратор платформы.
          </EmptyState>
        </div>
      </div>
    );
  }
  return <>{children}</>;
}
