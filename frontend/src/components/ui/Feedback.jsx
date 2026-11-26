import { AlertOctagon, Inbox, Loader2, RotateCw } from 'lucide-react';
import Button from './Button.jsx';

export function Spinner({ size = 18 }) {
  return <Loader2 size={size} className="spin" aria-hidden />;
}

export function FullPageLoader({ label = 'Chargement…' }) {
  return (
    <div className="fullpage-loader">
      <Spinner size={26} />
      <span>{label}</span>
    </div>
  );
}

export function LoadingBlock({ label = 'Chargement…' }) {
  return (
    <div className="loading-block">
      <Spinner />
      <span>{label}</span>
    </div>
  );
}

export function EmptyState({ icon: Icon = Inbox, title, text, action }) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon size={22} />
      </span>
      {title && <h4>{title}</h4>}
      {text && <p>{text}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  return (
    <div className="error-state">
      <AlertOctagon size={20} />
      <div>
        <strong>Impossible de charger les données</strong>
        <p>{error?.message || String(error)}</p>
      </div>
      {onRetry && (
        <Button icon={RotateCw} size="sm" onClick={onRetry}>
          Réessayer
        </Button>
      )}
    </div>
  );
}
