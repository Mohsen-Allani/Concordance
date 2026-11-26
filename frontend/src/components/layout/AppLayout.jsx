import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  BookOpen,
  ChevronDown,
  ClipboardCheck,
  FileStack,
  Home,
  LayoutDashboard,
  LogOut,
  Plus,
} from 'lucide-react';

import { useAuth } from '../../context/AuthContext.jsx';
import { getStats } from '../../api/client.js';
import Logo from '../brand/Logo.jsx';

const NAV = [
  { to: '/app', label: 'Tableau de bord', icon: LayoutDashboard, end: true },
  { to: '/app/analyses', label: 'Historique', icon: FileStack, end: true },
  { to: '/app/revisions', label: 'À réviser', icon: ClipboardCheck, badge: 'review' },
];

function initials(name = '') {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
}

function UserMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const close = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false);
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  return (
    <div className="usermenu" ref={ref}>
      <button className="usermenu-trigger" onClick={() => setOpen((o) => !o)}>
        <span className="avatar">{initials(user?.nom) || '·'}</span>
        <span className="usermenu-who">
          <strong>{user?.nom}</strong>
          <small>{user?.role}</small>
        </span>
        <ChevronDown size={15} />
      </button>
      {open && (
        <div className="usermenu-pop">
          <div className="usermenu-head">
            <strong>{user?.nom}</strong>
            <span>{user?.email}</span>
          </div>
          <button className="usermenu-item" onClick={() => navigate('/')}>
            <Home size={15} /> Page d'accueil
          </button>
          <a className="usermenu-item" href="/api/docs" target="_blank" rel="noreferrer">
            <BookOpen size={15} /> Documentation de l'API
          </a>
          <button className="usermenu-item usermenu-danger" onClick={logout}>
            <LogOut size={15} /> Se déconnecter
          </button>
        </div>
      )}
    </div>
  );
}

export default function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const [reviewCount, setReviewCount] = useState(null);

  // Le compteur « À réviser » est rafraîchi à chaque changement de page.
  useEffect(() => {
    getStats()
      .then((s) => setReviewCount(s.a_reviser))
      .catch(() => {});
  }, [location.pathname]);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);

  return (
    <div className="app">
      <header className="appbar">
        <div className="appbar-inner">
          <Link to="/app" className="appbar-brand">
            <Logo size={32} />
          </Link>

          <nav className="appnav">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) => `appnav-link ${isActive ? 'appnav-link-active' : ''}`}
              >
                <item.icon size={16} />
                <span>{item.label}</span>
                {item.badge === 'review' && reviewCount > 0 && <span className="appnav-badge">{reviewCount}</span>}
              </NavLink>
            ))}
          </nav>

          <div className="appbar-right">
            <button className="appbar-cta" onClick={() => navigate('/app/analyses/nouvelle')}>
              <Plus size={16} />
              <span>Nouvelle analyse</span>
            </button>
            <UserMenu />
          </div>
        </div>
      </header>

      <main className="content">
        <Outlet />
      </main>

      <footer className="appfoot">
        <span>Concordance · rapprochement automatique BC · BL · Facture</span>
        <span>v1.0</span>
      </footer>
    </div>
  );
}
