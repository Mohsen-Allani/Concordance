/* Logo : deux cercles qui se recouvrent (la concordance de deux pièces)
 * et une coche ambre (le contrôle). */
export function LogoMark({ size = 34 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className="logo-mark">
      <defs>
        <linearGradient id="logo-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#0f766e" />
          <stop offset="1" stopColor="#14b8a6" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="url(#logo-g)" />
      <circle cx="12.5" cy="16" r="6" fill="none" stroke="#fff" strokeWidth="2.2" />
      <circle cx="19.5" cy="16" r="6" fill="none" stroke="#fff" strokeWidth="2.2" opacity=".72" />
      <path d="m14 16.2 1.6 1.6 3-3.2" fill="none" stroke="#f59e0b" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function Logo({ light = false, size = 34, subtitle = true }) {
  return (
    <span className={`logo ${light ? 'logo-light' : ''}`}>
      <LogoMark size={size} />
      <span className="logo-text">
        <span className="logo-name">Concordance</span>
        {subtitle && <span className="logo-sub">BC · BL · Facture</span>}
      </span>
    </span>
  );
}
