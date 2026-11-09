import { Link, Route, Routes } from "react-router-dom";
import { RequireAuth } from "./auth/RequireAuth";
import { EmptyState } from "./components/Feedback";
import { Layout } from "./components/Layout";
import { LoginPage, RegisterPage } from "./pages/AuthPages";
import { AssignmentPage, ExpertPage } from "./pages/ExpertPages";
import { HackathonPage } from "./pages/HackathonPage";
import { HomePage } from "./pages/HomePage";
import { LeaderboardPage } from "./pages/LeaderboardPage";
import { NotificationsPage } from "./pages/NotificationsPage";
import { OrganizerHackathonPage } from "./pages/OrganizerHackathonPage";
import { OrganizerPage } from "./pages/OrganizerPage";
import { ProfilePage } from "./pages/ProfilePage";
import { TeamPage } from "./pages/TeamPage";
import { TeamsPage } from "./pages/TeamsPage";

function NotFound() {
  return (
    <div className="page narrow">
      <div className="card">
        <EmptyState
          icon="alert"
          title="Страница не найдена"
          action={
            <Link to="/" className="btn btn-primary">
              На главную
            </Link>
          }
        />
      </div>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        {/* Наблюдатель: публичные страницы без входа */}
        <Route index element={<HomePage />} />
        <Route path="hackathons/:id" element={<HackathonPage />} />
        <Route path="hackathons/:id/leaderboard" element={<LeaderboardPage />} />
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />

        {/* Любой вошедший пользователь */}
        <Route path="profile" element={<RequireAuth><ProfilePage /></RequireAuth>} />
        <Route path="notifications" element={<RequireAuth><NotificationsPage /></RequireAuth>} />

        {/* Участник и капитан */}
        <Route path="teams" element={<RequireAuth roles={["participant"]}><TeamsPage /></RequireAuth>} />
        <Route path="teams/:id" element={<RequireAuth><TeamPage /></RequireAuth>} />

        {/* Эксперт */}
        <Route path="expert" element={<RequireAuth roles={["expert"]}><ExpertPage /></RequireAuth>} />
        <Route path="expert/assignments/:id" element={<RequireAuth roles={["expert"]}><AssignmentPage /></RequireAuth>} />

        {/* Организатор */}
        <Route path="organizer" element={<RequireAuth roles={["organizer"]}><OrganizerPage /></RequireAuth>} />
        <Route
          path="organizer/hackathons/:id"
          element={<RequireAuth roles={["organizer"]}><OrganizerHackathonPage /></RequireAuth>}
        />

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
