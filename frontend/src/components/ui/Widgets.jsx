import { Search } from 'lucide-react';

export function KpiCard({ label, value, unit, hint, tone = 'neutral', icon: Icon, onClick }) {
  return (
    <div
      className={`kpi kpi-${tone} ${onClick ? 'kpi-clickable' : ''}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={(e) => onClick && e.key === 'Enter' && onClick()}
    >
      <div className="kpi-top">
        <span className="kpi-label">{label}</span>
        {Icon && (
          <span className="kpi-icon">
            <Icon size={16} />
          </span>
        )}
      </div>
      <div className="kpi-value">
        {value}
        {unit && <span className="kpi-unit">{unit}</span>}
      </div>
      {hint && <div className="kpi-hint">{hint}</div>}
    </div>
  );
}

/* Score de confiance 0..1 : barre + valeur. */
export function ConfidenceMeter({ value, compact = false }) {
  if (value === null || value === undefined) return <span className="text-muted">—</span>;
  const pct = Math.round(value * 100);
  const tone = value >= 0.9 ? 'ok' : value >= 0.75 ? 'warn' : 'err';
  return (
    <span className={`meter meter-${tone} ${compact ? 'meter-compact' : ''}`} title={`Confiance ${pct} %`}>
      <span className="meter-track">
        <span className="meter-fill" style={{ width: `${pct}%` }} />
      </span>
      <span className="meter-value">{pct} %</span>
    </span>
  );
}

export function FilterChips({ options, value, onChange }) {
  return (
    <div className="chips">
      {options.map((o) => (
        <button
          key={o.key}
          type="button"
          className={`chip ${value === o.key ? 'chip-active' : ''} ${o.tone ? `chip-${o.tone}` : ''}`}
          onClick={() => onChange(o.key)}
          disabled={o.disabled}
        >
          {o.label}
          {o.count !== undefined && <span className="chip-count">{o.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function SearchInput({ value, onChange, placeholder = 'Rechercher…' }) {
  return (
    <label className="search">
      <Search size={15} />
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
    </label>
  );
}

/* Barre empilée de répartition (statuts de produits, etc.). */
export function StackBar({ segments, height = 10 }) {
  const total = segments.reduce((s, x) => s + x.value, 0);
  if (!total) return <div className="stackbar stackbar-empty" style={{ height }} />;
  return (
    <div className="stackbar" style={{ height }}>
      {segments
        .filter((s) => s.value > 0)
        .map((s) => (
          <span
            key={s.key}
            className={`stackbar-seg seg-${s.tone}`}
            style={{ width: `${(100 * s.value) / total}%` }}
            title={`${s.label} : ${s.value}`}
          />
        ))}
    </div>
  );
}

export function KeyValue({ label, children, mono = false }) {
  return (
    <div className="kv">
      <dt>{label}</dt>
      <dd className={mono ? 'mono' : ''}>{children ?? '—'}</dd>
    </div>
  );
}
