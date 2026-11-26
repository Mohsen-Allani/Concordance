/* Histogramme groupé des 8 dernières semaines (SVG, sans dépendance). */
export default function ActivityChart({ weeks = [] }) {
  const W = 640;
  const H = 220;
  const pad = { top: 16, right: 8, bottom: 28, left: 30 };
  const innerW = W - pad.left - pad.right;
  const innerH = H - pad.top - pad.bottom;

  const max = Math.max(1, ...weeks.map((w) => w.analyses));
  const step = max <= 4 ? 1 : Math.ceil(max / 4);
  const top = Math.ceil(max / step) * step;
  const ticks = [];
  for (let v = 0; v <= top; v += step) ticks.push(v);

  const slot = innerW / Math.max(1, weeks.length);
  const barW = Math.min(18, slot / 3.2);
  const y = (v) => pad.top + innerH - (innerH * v) / top;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="Activité hebdomadaire">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={pad.left} x2={W - pad.right} y1={y(t)} y2={y(t)} className="chart-grid" />
          <text x={pad.left - 8} y={y(t) + 4} className="chart-axis" textAnchor="end">
            {t}
          </text>
        </g>
      ))}
      {weeks.map((w, i) => {
        const cx = pad.left + slot * i + slot / 2;
        return (
          <g key={w.label}>
            <rect x={cx - barW - 2} y={y(w.analyses)} width={barW} height={Math.max(0, y(0) - y(w.analyses))} rx="3" className="chart-bar-a">
              <title>{`${w.label} : ${w.analyses} analyse(s)`}</title>
            </rect>
            <rect x={cx + 2} y={y(w.avec_ecarts)} width={barW} height={Math.max(0, y(0) - y(w.avec_ecarts))} rx="3" className="chart-bar-b">
              <title>{`${w.label} : ${w.avec_ecarts} avec écarts`}</title>
            </rect>
            <text x={cx} y={H - 8} className="chart-axis" textAnchor="middle">
              {w.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
