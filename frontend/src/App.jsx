import { Navigate, Route, Routes, useLocation } from 'react-router-dom';

import { useAuth } from './context/AuthContext.jsx';
import AppLayout from './components/layout/AppLayout.jsx';
import { FullPageLoader } from './components/ui/Feedback.jsx';
import ErrorBoundary from './components/ErrorBoundary.jsx';

import LandingPage from './pages/landing/LandingPage.jsx';
import LoginPage from './pages/LoginPage.jsx';
import DashboardPage from './pages/DashboardPage.jsx';
import NewAnalysisPage from './pages/NewAnalysisPage.jsx';
import HistoryPage from './pages/HistoryPage.jsx';
import ReviewQueuePage from './pages/ReviewQueuePage.jsx';
import AnalysisPage from './pages/analysis/AnalysisPage.jsx';
import NotFoundPage from './pages/NotFoundPage.jsx';

function RequireAuth({ children }) {
  const { status } = useAuth();
  const location = useLocation();
  if (status === 'loading') return <FullPageLoader label="Ouverture de la session…" />;
  if (status !== 'authenticated') {
    return <Navigate to="/connexion" replace state={{ from: location }} />;
  }
  return children;
}

/* Plan du site :
 *   /            page d'accueil publique (présentation du projet)
 *   /connexion   connexion
 *   /app/...     espace de travail, réservé aux utilisateurs connectés */
export default function App() {
  const location = useLocation();

  return (
    <ErrorBoundary resetKey={location.pathname}>
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/connexion" element={<LoginPage />} />
      <Route
        path="/app"
        element={
          <RequireAuth>
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="analyses" element={<HistoryPage />} />
        <Route path="analyses/nouvelle" element={<NewAnalysisPage />} />
        <Route path="analyses/:id" element={<AnalysisPage />} />
        <Route path="revisions" element={<ReviewQueuePage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </ErrorBoundary>
  );
}
