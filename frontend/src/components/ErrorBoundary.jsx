import { Component } from 'react';
import { AlertOctagon, Home, RotateCw } from 'lucide-react';

/* Filet de sécurité : une erreur d'affichage montre un message clair
 * au lieu d'une page blanche. Réinitialisé à chaque changement de page. */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('Erreur d’affichage :', error, info?.componentStack);
  }

  componentDidUpdate(prev) {
    if (this.state.error && prev.resetKey !== this.props.resetKey) {
      this.setState({ error: null });
    }
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="crash">
        <div className="crash-card">
          <span className="crash-icon">
            <AlertOctagon size={26} />
          </span>
          <h1>Cette page n’a pas pu s’afficher</h1>
          <p>Une erreur inattendue s’est produite dans l’interface. Vos données ne sont pas affectées.</p>
          <code>{String(this.state.error?.message || this.state.error)}</code>
          <div className="crash-actions">
            <button className="btn btn-secondary btn-md" onClick={() => (window.location.href = '/')}>
              <Home size={16} /> Accueil
            </button>
            <button className="btn btn-primary btn-md" onClick={() => window.location.reload()}>
              <RotateCw size={16} /> Recharger la page
            </button>
          </div>
        </div>
      </div>
    );
  }
}
