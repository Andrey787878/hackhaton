import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { authApi, type RegisterInput } from "../api/auth";
import { ApiError } from "../api/errors";
import type { User } from "../api/types";
import { getTokens, onTokensChange, setTokens } from "./tokenStorage";

interface AuthValue {
  user: User | null;
  /** true, пока восстанавливаем сессию из сохранённых токенов. */
  initializing: boolean;
  login: (username: string, password: string) => Promise<User>;
  register: (data: RegisterInput) => Promise<User>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  setUser: (user: User) => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [initializing, setInitializing] = useState(() => getTokens() !== null);

  const refreshUser = useCallback(async () => {
    if (!getTokens()) {
      setUser(null);
      return;
    }
    try {
      setUser(await authApi.me());
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        setTokens(null);
        setUser(null);
      }
    }
  }, []);

  useEffect(() => {
    if (!getTokens()) return;
    refreshUser().finally(() => setInitializing(false));
  }, [refreshUser]);

  // Выход в другой вкладке или неудачный refresh очищают пользователя.
  useEffect(
    () =>
      onTokensChange((tokens) => {
        if (!tokens) setUser(null);
      }),
    [],
  );

  const login = useCallback(async (username: string, password: string) => {
    const result = await authApi.login(username, password);
    setTokens({ access: result.access_token, refresh: result.refresh_token });
    setUser(result.user);
    return result.user;
  }, []);

  const register = useCallback(
    async (data: RegisterInput) => {
      await authApi.register(data);
      return login(data.username, data.password);
    },
    [login],
  );

  const logout = useCallback(async () => {
    try {
      if (getTokens()) await authApi.logout();
    } catch {
      // сессия могла уже истечь — локальный выход выполняем в любом случае
    } finally {
      setTokens(null);
      setUser(null);
    }
  }, []);

  const value = useMemo(
    () => ({ user, initializing, login, register, logout, refreshUser, setUser }),
    [user, initializing, login, register, logout, refreshUser],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth вне AuthProvider");
  return context;
}
