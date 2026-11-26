/* Client de l'API FastAPI de Concordance.
 *
 * Toutes les routes sont celles du backend existant (voir docs/api.md) ;
 * aucune n'est ajoutée ni modifiée. Le jeton JWT est conservé dans le
 * localStorage et envoyé dans l'en-tête Authorization. */

const TOKEN_KEY = 'concordance.token';

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

let onUnauthorized = () => {};
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

/* FastAPI renvoie `detail` en chaîne (HTTPException) ou en liste
 * (erreurs de validation 422). */
function formatDetail(detail) {
  if (!detail) return null;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg || JSON.stringify(d)).join(' ; ');
  return JSON.stringify(detail);
}

async function request(path, { method = 'GET', body, headers = {}, raw = false } = {}) {
  const token = tokenStore.get();
  const h = { ...headers };
  if (token) h.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(path, { method, body, headers: h });
  } catch {
    throw new ApiError(
      "Serveur injoignable. Vérifiez que l'application tourne (docker compose up).",
      0,
    );
  }

  if (res.status === 401 && token) {
    tokenStore.clear();
    onUnauthorized();
    throw new ApiError('Session expirée, veuillez vous reconnecter.', 401);
  }
  if (!res.ok) {
    let msg = res.statusText || `Erreur ${res.status}`;
    try {
      msg = formatDetail((await res.json()).detail) || msg;
    } catch {
      /* corps non JSON */
    }
    if (res.status >= 500 && res.status !== 503 && msg === res.statusText) {
      msg = `Erreur interne du serveur (${res.status}). Consultez les logs : docker compose logs app`;
    }
    throw new ApiError(msg, res.status);
  }
  if (raw) return res;
  if (res.status === 204) return null;
  return res.json();
}

/* ------------------------------------------------------------ auth */

export async function login(email, password) {
  tokenStore.clear();
  const body = new URLSearchParams({ username: email, password });
  const data = await request('/api/auth/token', { method: 'POST', body });
  tokenStore.set(data.access_token);
  return data.utilisateur;
}

export const me = () => request('/api/auth/me');

/* -------------------------------------------------------- analyses */

export const getStats = () => request('/api/stats');
export const listAnalyses = () => request('/api/analyses');
export const getAnalysis = (id) => request(`/api/analyses/${id}`);
export const getJob = (jobId) => request(`/api/analyses/jobs/${jobId}`);

export function uploadAnalysis(file) {
  const form = new FormData();
  form.append('fichier', file, file.name);
  return request('/api/analyses', { method: 'POST', body: form });
}

/* Le corps est l'état COMPLET des révisions (pas un delta). */
export function saveRevisions(id, revisions) {
  return request(`/api/analyses/${id}/revisions`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(revisions),
  });
}

export async function downloadReport(id, fichier) {
  const res = await request(`/api/analyses/${id}/rapport`, { raw: true });
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `rapport_${(fichier || 'analyse').replace(/\.pdf$/i, '')}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
