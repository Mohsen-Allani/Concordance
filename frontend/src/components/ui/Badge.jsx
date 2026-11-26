import { analysisStatus, DOC, productStatus } from '../../lib/status.js';

export function Badge({ tone = 'muted', dot = true, children, title, className = '' }) {
  return (
    <span className={`badge badge-${tone} ${className}`} title={title}>
      {dot && <span className="badge-dot" />}
      {children}
    </span>
  );
}

export function AnalysisStatusBadge({ analysis }) {
  const s = analysisStatus(analysis);
  return <Badge tone={s.tone}>{s.label}</Badge>;
}

export function ProductStatusBadge({ statut }) {
  const s = productStatus(statut);
  return <Badge tone={s.tone}>{s.label}</Badge>;
}

export function DocTag({ type, size = 'md' }) {
  const meta = DOC[type];
  return (
    <span className={`doctag doctag-${(meta?.tag || type).toLowerCase()} doctag-${size}`} title={meta?.label}>
      {meta?.tag || type}
    </span>
  );
}

export function DocSet({ types = [] }) {
  return (
    <span className="docset">
      {types.map((t) => (
        <DocTag key={t} type={t} size="sm" />
      ))}
    </span>
  );
}
