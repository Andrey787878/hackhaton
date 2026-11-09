import { useState, type FormEvent, type ReactNode } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError, messageOf } from "../api/errors";
import { useAuth } from "../auth/AuthContext";
import { Alert } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { passwordProblems, USERNAME } from "../utils/validation";


function AuthShell({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="page auth-page">
      <div className="auth-card card">
        <div className="auth-mark">
          <Icon name="bolt" size={22} />
        </div>
        <h1>{title}</h1>
        <p className="muted">{subtitle}</p>
        {children}
      </div>
    </div>
  );
}

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/";
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={from} replace />;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username.trim(), password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError && (err.status === 401 || err.status === 422)
          ? "Неверный логин или пароль."
          : messageOf(err),
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Вход" subtitle="Участники, эксперты и организаторы входят по логину.">
      <form className="form" onSubmit={submit}>
        <label className="field">
          <span>Логин</span>
          <input autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
        </label>
        <label className="field">
          <span>Пароль</span>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && <Alert tone="error">{error}</Alert>}
        <button className="btn btn-primary btn-block btn-lg" disabled={busy}>
          {busy ? "Входим…" : "Войти"}
        </button>
      </form>
      <p className="muted small center">
        Нет аккаунта? <Link to="/register">Зарегистрироваться</Link>
      </p>
    </AuthShell>
  );
}

export function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    username: "",
    email: "",
    display_name: "",
    birthday: "",
    password: "",
    c_password: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const set = (key: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm((prev) => ({ ...prev, [key]: event.target.value }));

  const validate = (): Record<string, string> => {
    const result: Record<string, string> = {};
    if (!USERNAME.test(form.username)) result.username = "3–64 латинских символа, цифры, _ или -; начало — буква или цифра";
    const problems = passwordProblems(form.password);
    if (problems.length) result.password = `Нужно: ${problems.join(", ")}`;
    if (form.password !== form.c_password) result.c_password = "Пароли не совпадают";
    if (form.birthday && form.birthday > new Date().toISOString().slice(0, 10)) result.birthday = "Дата не может быть в будущем";
    return result;
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const local = validate();
    setErrors(local);
    setError(null);
    if (Object.keys(local).length) return;
    setBusy(true);
    try {
      await register({
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password,
        c_password: form.c_password,
        display_name: form.display_name.trim() || null,
        birthday: form.birthday || null,
      });
      navigate("/", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) setErrors(err.fields);
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  };

  const problems = form.password ? passwordProblems(form.password) : [];

  return (
    <AuthShell title="Регистрация" subtitle="Новый аккаунт получает роль участника.">
      <form className="form" onSubmit={submit} noValidate>
        <div className="form-row">
          <label className={errors.username ? "field invalid" : "field"}>
            <span>Логин *</span>
            <input autoComplete="username" value={form.username} onChange={set("username")} required />
            {errors.username && <small>{errors.username}</small>}
          </label>
          <label className={errors.email ? "field invalid" : "field"}>
            <span>Email *</span>
            <input type="email" autoComplete="email" value={form.email} onChange={set("email")} required />
            {errors.email && <small>{errors.email}</small>}
          </label>
        </div>
        <div className="form-row">
          <label className={errors.display_name ? "field invalid" : "field"}>
            <span>Отображаемое имя</span>
            <input value={form.display_name} onChange={set("display_name")} maxLength={128} />
          </label>
          <label className={errors.birthday ? "field invalid" : "field"}>
            <span>Дата рождения</span>
            <input type="date" value={form.birthday} onChange={set("birthday")} />
            {errors.birthday && <small>{errors.birthday}</small>}
          </label>
        </div>
        <label className={errors.password ? "field invalid" : "field"}>
          <span>Пароль *</span>
          <input type="password" autoComplete="new-password" value={form.password} onChange={set("password")} required />
          {errors.password ? (
            <small>{errors.password}</small>
          ) : (
            form.password && (
              <small className={problems.length ? "hint" : "hint ok"}>
                {problems.length ? `Ещё нужно: ${problems.join(", ")}` : "Пароль подходит"}
              </small>
            )
          )}
        </label>
        <label className={errors.c_password ? "field invalid" : "field"}>
          <span>Повтор пароля *</span>
          <input type="password" autoComplete="new-password" value={form.c_password} onChange={set("c_password")} required />
          {errors.c_password && <small>{errors.c_password}</small>}
        </label>
        {error && <Alert tone="error">{error}</Alert>}
        <button className="btn btn-primary btn-block btn-lg" disabled={busy}>
          {busy ? "Создаём аккаунт…" : "Создать аккаунт"}
        </button>
      </form>
      <p className="muted small center">
        Уже зарегистрированы? <Link to="/login">Войти</Link>
      </p>
    </AuthShell>
  );
}
