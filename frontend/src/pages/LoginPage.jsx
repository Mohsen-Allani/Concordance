import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  FileSearch,
  GitCompareArrows,
  Lock,
  LogOut,
  Mail,
  ShieldCheck,
} from 'lucide-react';

import { useAuth } from '../context/AuthContext.jsx';
import Button from '../components/ui/Button.jsx';
import Logo from '../components/brand/Logo.jsx';
import { ReportCard } from './landing/Illustrations.jsx';

const POINTS = [
  { icon: FileSearch, title: 'Lecture automatique', text: 'BC, BL et factures, natifs ou scannés.' },
  { icon: ShieldCheck, title: 'Contrôle arithmétique', text: 'Quantités, prix, remises, TVA et totaux.' },
  { icon: GitCompareArrows, title: 'Rapprochement trois voies', text: 'Chaque ligne confrontée à la commande.' },
];

export default function LoginPage() {
  const { login, logout, status, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await login(email.trim(), password);
      navigate(location.state?.from?.pathname || '/app', { replace: true });
    } catch (err) {
      setError(err.message || 'Connexion refusée');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <section className="login-aside">
        <Link to="/" className="login-logo">
          <Logo light size={36} />
        </Link>

        <div className="login-pitch">
          <span className="pill pill-dark">Espace de contrôle</span>
          <h1>
            Ce qui est commandé, livré et facturé, <em>enfin d'accord.</em>
          </h1>
          <p>Connectez-vous pour déposer vos documents et suivre vos contrôles.</p>
        </div>

        <div className="login-visual">
          <ReportCard compact />
        </div>

        <ul className="login-points">
          {POINTS.map((p) => (
            <li key={p.title}>
              <span className="login-point-icon">
                <p.icon size={17} />
              </span>
              <div>
                <strong>{p.title}</strong>
                <span>{p.text}</span>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="login-main">
        <Link to="/" className="login-back">
          <ArrowLeft size={15} /> Retour à l'accueil
        </Link>

        {status === 'authenticated' ? (
          <div className="login-form">
            <div className="login-form-head">
              <h2>Vous êtes déjà connecté</h2>
              <p>
                Session ouverte au nom de <b>{user?.nom}</b>
                {user?.email ? ` (${user.email})` : ''}.
              </p>
            </div>
            <Button variant="primary" size="lg" className="btn-block" icon={ArrowRight} onClick={() => navigate('/app')}>
              Accéder à mon espace
            </Button>
            <Button size="lg" className="btn-block" icon={LogOut} onClick={logout}>
              Changer de compte
            </Button>
          </div>
        ) : (
        <form className="login-form" onSubmit={submit}>
          <div className="login-form-head">
            <h2>Bon retour 👋</h2>
            <p>Identifiez-vous avec votre compte professionnel.</p>
          </div>

          <label className="field">
            <span className="field-label">Adresse e-mail</span>
            <span className="input-icon">
              <Mail size={16} />
              <input
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="prenom.nom@entreprise.com"
              />
            </span>
          </label>
          <label className="field">
            <span className="field-label">Mot de passe</span>
            <span className="input-icon">
              <Lock size={16} />
              <input
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </span>
          </label>

          {error && (
            <div className="form-error">
              <AlertCircle size={16} /> {error}
            </div>
          )}

          <Button type="submit" variant="primary" size="lg" loading={busy} className="btn-block">
            Se connecter
          </Button>
          <p className="login-help">
            Pas encore de compte ? Il est créé par l'administrateur avec{' '}
            <code>concordance create-user</code>.
          </p>
        </form>
        )}
      </section>
    </div>
  );
}
