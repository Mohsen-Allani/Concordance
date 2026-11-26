/* Contrat d'affichage — identique à l'ancienne interface et au rapport PDF :
 *   quantité : sans décimales inutiles        ("4.000"  -> "4")
 *   montants : 3 décimales fixes, virgule     ("37.5"   -> "37,500")
 *   taux     : nombre nu, sans zéros inutiles ("15.000" -> "15")
 * Les valeurs arrivent de l'API sous forme de chaînes (Decimal sérialisés). */

const EMPTY = '—';
const isEmpty = (v) => v === null || v === undefined || v === '';

function stripZeros(v) {
  let t = String(v);
  if (t.includes('.')) t = t.replace(/0+$/, '').replace(/\.$/, '');
  return t;
}

export function fmtQty(v) {
  if (isEmpty(v)) return EMPTY;
  return stripZeros(v).replace('.', ',');
}

export function fmtMoney(v) {
  if (isEmpty(v)) return EMPTY;
  const n = parseFloat(String(v).replace(',', '.'));
  if (Number.isNaN(n)) return String(v);
  const [ent, dec] = Math.abs(n).toFixed(3).split('.');
  const groups = ent.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  return `${n < 0 ? '−' : ''}${groups},${dec}`;
}

export function fmtRate(v) {
  if (isEmpty(v)) return EMPTY;
  return stripZeros(v).replace('.', ',');
}

export function fmtSigned(v, formatter = fmtMoney) {
  const n = parseFloat(v);
  if (Number.isNaN(n)) return EMPTY;
  if (n === 0) return formatter(0);
  return `${n > 0 ? '+' : '−'}${formatter(Math.abs(n))}`;
}

export function fmtDate(iso) {
  if (!iso) return EMPTY;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

export function fmtDateTime(iso) {
  if (!iso) return EMPTY;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return `${fmtDate(iso)} · ${d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}`;
}

export function fmtRelative(iso) {
  if (!iso) return EMPTY;
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (Number.isNaN(diff)) return EMPTY;
  if (diff < 60) return "à l'instant";
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `il y a ${Math.floor(diff / 3600)} h`;
  if (diff < 7 * 86400) return `il y a ${Math.floor(diff / 86400)} j`;
  return fmtDate(iso);
}

export function fmtPercent(v, digits = 0) {
  if (v === null || v === undefined || Number.isNaN(v)) return EMPTY;
  return `${(v * 100).toFixed(digits).replace('.', ',')} %`;
}

export function fmtBytes(n) {
  if (!n && n !== 0) return EMPTY;
  if (n < 1024) return `${n} o`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} Ko`;
  return `${(n / 1024 / 1024).toFixed(1).replace('.', ',')} Mo`;
}

export function plural(n, singular, pluralForm) {
  return `${n} ${n > 1 ? pluralForm || `${singular}s` : singular}`;
}
