/* Concordance — interface web.
 *
 * Rendu par état : chaque vue est reconstruite depuis les données de l'API,
 * jamais retouchée à la main. Les gestes de révision (édition de valeur,
 * glisser-déposer, choix de candidat) ne modifient qu'un état local
 * `revState` ; « Enregistrer et recalculer » l'envoie tel quel au serveur,
 * qui rejoue la chaîne déterministe et renvoie le nouvel état. */

'use strict';

/* ============================== API ============================== */

let token = localStorage.getItem('token') || null;
let currentUser = null;

async function api(path, options = {}) {
  const headers = Object.assign({}, options.headers);
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const res = await fetch(path, Object.assign({}, options, { headers }));
  if (res.status === 401) { showLogin(); throw new Error('Session expirée'); }
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}

/* ============================ Helpers ============================ */

const $ = (s, el) => (el || document).querySelector(s);
const $$ = (s, el) => [...(el || document).querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

/* Contrat d'affichage — identique pour BC, BL et Facture :
 *   quantité   : entier, sans décimales inutiles      ("4.0"    -> "4")
 *   montants   : 3 décimales fixes, virgule           ("37.5"   -> "37,500")
 *   remise     : nombre nu en %, sans zéros inutiles  ("15.000" -> "15")
 * L'unité (%) de la remise est portée par l'en-tête de colonne. */

function stripZeros(v) {                   // "15.000" -> "15", "7.500" -> "7.5"
  let t = String(v);
  if (t.includes('.')) t = t.replace(/0+$/, '').replace(/\.$/, '');
  return t;
}
function fmtNum(v) {                       // brut, virgule décimale
  if (v === null || v === undefined || v === '') return '—';
  return String(v).replace('.', ',');
}
function fmtQty(v) {                       // quantité : sans zéros inutiles
  if (v === null || v === undefined || v === '') return '—';
  return stripZeros(v).replace('.', ',');
}
function fmtMoney(v) {                     // montants : 3 décimales fixes
  if (v === null || v === undefined || v === '') return '—';
  const n = parseFloat(String(v).replace(',', '.'));
  if (isNaN(n)) return esc(String(v));
  return n.toFixed(3).replace('.', ',');
}
function fmtRem(v) {                       // remise : nombre nu, sans zéros
  if (v === null || v === undefined || v === '') return '—';
  return stripZeros(v).replace('.', ',');
}
function fmtDate(iso, withTime) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d)) return esc(iso);
  const j = d.toLocaleDateString('fr-FR');
  return withTime
    ? j + ' ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
    : j;
}
const DOCTAG = { BC: 'BC', BL: 'BL', Facture: 'FA' };
const DOCLABEL = { BC: 'Bon de commande', BL: 'Bon de livraison', Facture: 'Facture' };
const PAIRE = { BL: 'BC↔BL', Facture: 'BC↔Facture' };

let tt;
function toast(msg, ok = true) {
  const t = $('#toastEl');
  t.innerHTML = (ok ? '<span class="ok-i">✓</span> ' : '⚠ ') + esc(msg);
  t.classList.add('on');
  clearTimeout(tt); tt = setTimeout(() => t.classList.remove('on'), 3200);
}

/* ============================ Navigation ========================= */

const titles = { dash: 'Tableau de bord', new: 'Nouvelle analyse',
                 res: 'Résultat de l\u2019analyse', hist: 'Historique' };

function go(v, crumb) {
  $$('.view').forEach(x => x.classList.remove('on'));
  $('#v-' + v).classList.add('on');
  $$('.nav a').forEach(a => a.classList.toggle('on', a.dataset.v === v));
  $('#topTitle').textContent = titles[v];
  $('#topCrumb').textContent = crumb || '';
  window.scrollTo(0, 0);
  if (v === 'dash') loadDashboard();
  if (v === 'hist') loadHistory();
}
document.addEventListener('click', e => {
  const a = e.target.closest('[data-v]');
  if (a && a.tagName === 'A') { e.preventDefault(); go(a.dataset.v); }
});

/* ============================== Login ============================ */

function showLogin() {
  token = null; localStorage.removeItem('token');
  $('#loginView').classList.add('on');
}
$('#loginForm').addEventListener('submit', async e => {
  e.preventDefault();
  $('#loginErr').textContent = '';
  const body = new URLSearchParams({ username: $('#em').value,
                                     password: $('#pw').value });
  try {
    const res = await fetch('/api/auth/token', { method: 'POST', body });
    if (!res.ok) {
      const j = await res.json().catch(() => ({}));
      throw new Error(j.detail || 'Connexion refusée');
    }
    const data = await res.json();
    token = data.access_token;
    localStorage.setItem('token', token);
    setUser(data.utilisateur);
    $('#loginView').classList.remove('on');
    $('#pw').value = '';
    go('dash');
  } catch (err) { $('#loginErr').textContent = err.message; }
});
$('#userBox').addEventListener('click', () => { showLogin(); });

function setUser(u) {
  currentUser = u;
  $('#userName').textContent = u.nom;
  $('#userRole').textContent = u.role;
  $('#userAvatar').textContent = u.nom.split(/\s+/).map(w => w[0]).join('')
                                  .slice(0, 2).toUpperCase();
}

async function boot() {
  if (!token) { showLogin(); return; }
  try { setUser(await api('/api/auth/me')); go('dash'); }
  catch (_) { /* showLogin déjà déclenché par api() */ }
}

/* ========================= Badges de statut ====================== */

function statutBadge(a) {
  const t = a.totaux || {};
  if (a.statut === 'en attente de révision')
    return '<span class="badge b-warn"><span class="dot"></span>À réviser</span>';
  if (a.statut === 'hors périmètre')
    return '<span class="badge b-mut"><span class="dot"></span>Hors périmètre</span>';
  if (a.statut === 'erreur')
    return '<span class="badge b-err"><span class="dot"></span>Erreur</span>';
  if ((t.ecarts || 0) > 0)
    return `<span class="badge b-err"><span class="dot"></span>${t.ecarts} écart(s)</span>`;
  return '<span class="badge b-ok"><span class="dot"></span>Conforme</span>';
}

function docset(types) {
  return '<span class="docset">' + (types || []).map(t =>
    `<i class="${t === 'BC' ? 'pri' : ''}">${DOCTAG[t] || t}</i>`).join('') + '</span>';
}

/* ========================= Tableau de bord ======================= */

async function loadDashboard() {
  $('#statCards').innerHTML = '<div class="loading"><div class="sp"></div>Chargement…</div>';
  let s;
  try { s = await api('/api/stats'); }
  catch (e) { $('#statCards').innerHTML = `<div class="empty">${esc(e.message)}</div>`; return; }

  $('#statCards').innerHTML = `
    <div class="card stat">
      <div class="ic blue"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/></svg></div>
      <div><div class="eyebrow">Analyses</div><div class="v num">${s.total}</div>
      <div class="d"><b style="color:var(--ok)">+${s.cette_semaine}</b> cette semaine</div></div>
    </div>
    <div class="card stat click" data-go="hist">
      <div class="ic amber"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg></div>
      <div><div class="eyebrow">À réviser</div><div class="v num" style="color:#c47c00">${s.a_reviser}</div>
      <div class="d">Ambiguïtés à trancher</div></div>
    </div>
    <div class="card stat">
      <div class="ic green"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M20 6 9 17l-5-5"/></svg></div>
      <div><div class="eyebrow">Produits conformes</div>
      <div class="v num">${s.pct_conformes ?? '—'}<span style="font-size:1rem">${s.pct_conformes === null ? '' : '%'}</span></div>
      <div class="d">${s.conformes} / ${s.produits} produits rapprochés</div></div>
    </div>
    <div class="card stat">
      <div class="ic red"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m12 3 10 18H2z"/><path d="M12 10v4m0 3h.01"/></svg></div>
      <div><div class="eyebrow">Écarts · ce mois</div><div class="v num" style="color:var(--err)">${s.ecarts_mois}</div>
      <div class="d">dont <b>${s.ecarts_prix_mois}</b> écarts de prix</div></div>
    </div>`;
  $('[data-go="hist"]', $('#statCards'))?.addEventListener('click', () => go('hist'));

  const max = Math.max(1, ...s.activite.map(w => w.analyses));
  $('#chart').innerHTML = s.activite.map(w => `
    <div class="bar"><div class="cols">
      <div class="c" style="height:${Math.round(100 * w.analyses / max)}%"></div>
      <div class="c e" style="height:${Math.round(100 * w.avec_ecarts / max)}%"></div>
    </div><div class="lb">${esc(w.label)}</div></div>`).join('');

  $('#recentList').innerHTML = s.recentes.length ? s.recentes.map(a => `
    <li data-id="${a.id}"><div class="f"><b>${esc(a.fichier)}</b>
      <small>${fmtDate(a.date, true)} · ${a.pages ?? '?'} page(s)</small></div>
      ${statutBadge(a)}</li>`).join('')
    : '<div class="empty">Aucune analyse pour l\u2019instant — déposez un premier PDF.</div>';
  $$('#recentList li').forEach(li =>
    li.addEventListener('click', () => openAnalysis(+li.dataset.id)));
}

/* =========================== Historique ========================== */

let histCache = [];

async function loadHistory() {
  $('#histBody').innerHTML = '<tr><td colspan="5"><div class="loading"><div class="sp"></div>Chargement…</div></td></tr>';
  try { histCache = await api('/api/analyses'); }
  catch (e) { $('#histBody').innerHTML = `<tr><td colspan="5" class="empty">${esc(e.message)}</td></tr>`; return; }
  renderHistory();
}

function renderHistory() {
  const f = $('#histFilters .fpill.on')?.dataset.f || 'toutes';
  const rows = histCache.filter(a => {
    const ecarts = (a.totaux || {}).ecarts || 0;
    if (f === 'reviser') return a.statut === 'en attente de révision';
    if (f === 'ecarts') return ecarts > 0;
    if (f === 'conformes') return a.statut === 'terminé' && ecarts === 0;
    return true;
  });
  $('#histBody').innerHTML = rows.length ? rows.map(a => `
    <tr data-id="${a.id}"><td><b>${esc(a.fichier)}</b></td>
      <td>${docset(a.documents)}</td>
      <td>${fmtDate(a.date, true)}</td>
      <td>${statutBadge(a)}</td>
      <td class="num" style="text-align:right">${a.confiance != null ? a.confiance.toFixed(2).replace('.', ',') : '—'}</td></tr>`).join('')
    : '<tr><td colspan="5" class="empty">Aucune analyse ne correspond à ce filtre.</td></tr>';
  $$('#histBody tr[data-id]').forEach(tr =>
    tr.addEventListener('click', () => openAnalysis(+tr.dataset.id)));
}
$$('#histFilters .fpill').forEach(b => b.addEventListener('click', () => {
  $$('#histFilters .fpill').forEach(x => x.classList.remove('on'));
  b.classList.add('on'); renderHistory();
}));

/* ======================= Dépôt et progression ==================== */

const dz = $('#dz');
dz.addEventListener('click', () => $('#fileInput').click());
dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('gover'); });
dz.addEventListener('dragleave', () => dz.classList.remove('gover'));
dz.addEventListener('drop', e => {
  e.preventDefault(); dz.classList.remove('gover');
  const f = e.dataTransfer.files?.[0];
  if (f) upload(f);
});
$('#fileInput').addEventListener('change', e => {
  if (e.target.files[0]) upload(e.target.files[0]);
  e.target.value = '';
});

function setStep(n, cls, detail) {
  const s = $('#st' + n);
  s.className = 'step ' + cls;
  s.querySelector('.n').textContent = cls === 'done' ? '✓' : n;
  if (detail) s.querySelector('small').textContent = detail;
}

async function upload(file) {
  if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf'))
    return toast('Seul un document PDF est accepté', false);
  if (file.size > 20 * 1024 * 1024)
    return toast('Fichier trop volumineux (20 Mo max.)', false);

  dz.style.display = 'none';
  $('#pipe').style.display = 'block';
  $('#pipeErr').classList.remove('on');
  $('#pipeFile').innerHTML = `<span class="mono">${esc(file.name)}</span>`;
  for (let i = 1; i <= 5; i++) setStep(i, 'wait');

  const form = new FormData();
  form.append('fichier', file, file.name);
  let job;
  try { job = (await api('/api/analyses', { method: 'POST', body: form })).job; }
  catch (e) { return pipeFail(e.message); }

  const poll = setInterval(async () => {
    let j;
    try { j = await api('/api/analyses/jobs/' + job); }
    catch (e) { clearInterval(poll); return pipeFail(e.message); }
    for (let i = 1; i <= 5; i++) {
      if (i < j.etape) setStep(i, 'done');
      else if (i === j.etape) setStep(i, j.statut === 'terminé' ? 'done' : 'run', j.detail);
      else setStep(i, 'wait');
    }
    if (j.statut === 'terminé') {
      clearInterval(poll);
      const r = j.resume || {};
      toast(r.status === 'hors périmètre'
        ? 'Document hors périmètre — voir le détail'
        : 'Analyse terminée');
      resetDrop();
      if (j.id_analyse) openAnalysis(j.id_analyse);
    } else if (j.statut === 'erreur') {
      clearInterval(poll);
      pipeFail(j.erreur || 'Le traitement a échoué');
    }
  }, 1200);
}
function pipeFail(msg) {
  const e = $('#pipeErr');
  e.textContent = 'Échec du traitement : ' + msg;
  e.classList.add('on');
  setTimeout(resetDrop, 6000);
}
function resetDrop() {
  dz.style.display = '';
  $('#pipe').style.display = 'none';
}

/* ============================ Résultats ==========================
 * `analysis` : dernier état renvoyé par l'API (source de rendu).
 * `revState` : révisions en construction (état complet, envoyé tel quel).
 * `pendingOps` : nombre de gestes depuis le dernier enregistrement.     */

let analysis = null;
let revState = { corrections: {}, rapprochements: {} };
let pendingOps = 0;

function freshRevState() {
  const r = analysis?.revisions;
  revState = r ? JSON.parse(JSON.stringify(r)) : {};
  revState.corrections = revState.corrections || {};
  revState.rapprochements = revState.rapprochements || {};
  pendingOps = 0;
  updateApplybar();
}
function updateApplybar() {
  $('#nbEdits').textContent = pendingOps;
  $('#applybar').classList.toggle('on', pendingOps > 0);
}

async function openAnalysis(id) {
  go('res');
  $('#resBody').innerHTML = '<div class="loading"><div class="sp"></div>Chargement de l\u2019analyse…</div>';
  try { analysis = await api('/api/analyses/' + id); }
  catch (e) { $('#resBody').innerHTML = `<div class="empty">${esc(e.message)}</div>`; return; }
  $('#topCrumb').textContent = 'Historique / ' + analysis.fichier;
  freshRevState();
  renderResults();
}

/* ---------- rendu principal ---------- */

function renderResults() {
  const a = analysis;
  const c = a.comparaison;
  let html = `
    <div class="res-top">
      <span class="file">${esc(a.fichier)}</span>
      <span class="when">${fmtDate(a.date, true)} · ${a.pages ?? '?'} page(s)</span>
      <span class="spacer"></span>`;
  if (c && c.totaux) html += `
      <div class="tally">
        <div class="t ok"><div class="v">${c.totaux.conformes}</div><div class="l">Conformes</div></div>
        <div class="t err"><div class="v">${c.totaux.ecarts}</div><div class="l">Écarts</div></div>
        <div class="t warn"><div class="v">${c.totaux.ambigus}</div><div class="l">À réviser</div></div>
      </div>`;
  html += '</div>';

  if (!c || c.statut === 'impossible') {
    html += `<div class="card scope-card"><h3>${a.statut === 'hors périmètre'
        ? 'Document hors du périmètre v1' : 'Comparaison impossible'}</h3><ul>`;
    const msgs = (a.erreurs || []).concat(c && c.message ? [c.message] : []);
    html += (msgs.length ? msgs : ['Le PDF doit contenir un Bon de Commande et au moins un Bon de Livraison ou une Facture.'])
      .map(m => `<li>${esc(m)}</li>`).join('');
    html += '</ul></div>';
    $('#resBody').innerHTML = html;
    return;
  }

  html += renderParties(a, c);
  html += renderLedger(a, c);
  html += renderLoose(a, c);
  html += renderSums(a, c);
  html += `
    <div class="res-foot">
      ${a.rapport ? `<button class="btn pri" id="btnRapport">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 4v12m0 0 5-5m-5 5-5-5"/><path d="M4 19h16"/></svg>
        Télécharger le rapport PDF</button>` : ''}
      <button class="btn" id="btnReplay">Rejouer l'analyse</button>
    </div>`;

  $('#resBody').innerHTML = html;
  bindResultEvents();
}

function docByType(t) {
  return (analysis.documents_detail || []).find(d => d.type === t);
}

function renderParties(a, c) {
  const bc = docByType('BC') || {};
  const four = bc.fournisseur || {}, cli = bc.client || {};
  const issues = (c.entete || []).filter(x => x.statut === 'warning');
  const chk = issues.length
    ? `<span class="chk warn"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="m12 3 10 18H2z"/></svg>${issues.length} contrôle(s) d'en-tête</span>`
    : `<span class="chk"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M20 6 9 17l-5-5"/></svg>En-têtes concordants</span>`;
  const devise = bc.devise || (analysis.documents_detail || []).map(d => d.devise).find(Boolean) || '—';
  const chips = (analysis.documents_detail || []).map(d => `
    <span class="docchip"><span class="k">${DOCTAG[d.type]}</span>
      <span class="mono">${esc(d.numero || 'sans nº')}</span>
      <span class="dt">${fmtDate(d.date)}</span></span>`).join('');
  return `
    <div class="card parties">
      <div class="party">
        <div class="role">Fournisseur</div>
        <div class="name">${esc(four.nom || '—')}</div>
        <div class="det">${four.matriculeFiscal ? 'MF <span class="mono">' + esc(four.matriculeFiscal) + '</span>' : ''}
          ${four.adresse ? (four.matriculeFiscal ? ' · ' : '') + esc(four.adresse) : ''}</div>
      </div>
      <div class="flow">
        <span class="arr"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 12h16m0 0-5-5m5 5-5 5"/></svg></span>
        ${chk}
      </div>
      <div class="party right">
        <div class="role">Client</div>
        <div class="name">${esc(cli.nom || '—')}</div>
        <div class="det">${cli.matriculeFiscal ? 'MF <span class="mono">' + esc(cli.matriculeFiscal) + '</span>' : ''}
          ${cli.adresse ? (cli.matriculeFiscal ? ' · ' : '') + esc(cli.adresse) : ''}</div>
      </div>
      ${issues.length ? `<div class="hd-issues">${issues.map(i => `<div>⚠ ${esc(i.message)}</div>`).join('')}</div>` : ''}
      <div class="docstrip">${chips}
        <span class="dev">Devise <b>${esc(devise)}</b> · montants HT</span></div>
    </div>`;
}

/* ---------- registre (produits appariés) ---------- */

function isLedgerProduct(p) {
  if (!p.cle.startsWith('BC:')) return false;
  const paires = Object.values(p.paires || {});
  const tousManquants = paires.length &&
    paires.every(x => x.statut === 'manquant');
  return !tousManquants;                    // BC seul partout -> non rapprochées
}

function lineCells(t, l, badAxes, corrigees) {
  const tag = DOCTAG[t];
  const editable = (l.lignes_source || []).length === 1;
  const origin = editable ? l.lignes_source[0] : null;
  const bad = f => badAxes.has(f) ? ' bad' : '';
  const val = (f, contenu, cls, raw) => editable
    ? `<div class="${cls} val${bad(f)}" data-f="${f}" data-doc="${t}" data-i="${origin}"
            data-v="${esc(raw ?? '')}">${contenu}</div>`
    : `<div class="${cls}${bad(f)}">${contenu}</div>`;
  const corrDot = corrigees ? '<span class="fuz" title="Valeur corrigée par l\u2019opérateur">✎</span>' : '';
  const fuz = l.fusionnee
    ? `<span class="fuz" title="Lignes d\u2019origine ${l.lignes_source.join(', ')} fusionnées sur la même référence">⇄ fusion</span>` : '';
  return `
    <div class="lrow" data-doc="${tag}" data-type="${t}"
         ${(l.lignes_source || []).length ? 'draggable="true"' : ''}
         data-src="${(l.lignes_source || []).join(',')}">
      <div><span class="doctag">${tag}</span></div>
      ${val('reference', esc(l.reference || '—'), 'ref', l.reference)}
      <div class="des">${editable
          ? `<span class="val" data-f="designation" data-doc="${t}" data-i="${origin}" data-v="${esc(l.designation ?? '')}">${esc(l.designation || '—')}</span>`
          : `<span>${esc(l.designation || '—')}</span>`}${fuz}${corrDot}</div>
      ${val('quantite', fmtQty(l.quantite), 'num', l.quantite)}
      ${val('unite', esc(l.unite || '—'), 'unitc', l.unite)}
      ${val('prixUnitaireHT', fmtMoney(l.prixUnitaireHT), 'num', l.prixUnitaireHT)}
      ${val('tauxRemise', fmtRem(l.tauxRemise), 'num', l.tauxRemise)}
      <div class="num${bad('montantHT')}">${fmtMoney(l.montantHT)}</div>
    </div>`;
}

function ecartAxes(p) {
  /* champs en écart par document cible : { Facture: Set(champs), BL: ... } */
  const out = { BL: new Set(), Facture: new Set(), BC: new Set() };
  for (const t of ['BL', 'Facture']) {
    const paire = (p.paires || {})[PAIRE[t]];
    for (const ax of paire?.axes || [])
      if (ax.statut === 'écart') out[t].add(ax.champ);
  }
  return out;
}

function verdictOf(p) {
  const s = p.statut;
  if (s === 'conforme')
    return { cls: 'v-ok', badge: 'b-ok', label: 'Conforme',
             small: 'Quantités et prix concordants' };
  if (s === 'ambigu') {
    const nb = Object.values(p.paires || {})
      .filter(x => x.statut === 'ambigu').length;
    return { cls: 'v-warn', badge: 'b-warn', label: 'À réviser',
             small: nb > 1 ? 'Deux rapprochements non tranchés' : 'Rapprochement non tranché' };
  }
  if (s === 'écart' || s === 'manquant') {
    const morceaux = [];
    let label = 'Écart';
    for (const t of ['BL', 'Facture']) {
      const paire = (p.paires || {})[PAIRE[t]];
      if (!paire) continue;
      if (paire.statut === 'manquant') {
        morceaux.push(t === 'BL' ? 'non livré' : 'non facturé'); continue;
      }
      for (const ax of paire.axes || []) {
        if (ax.statut !== 'écart') continue;
        const signe = parseFloat(ax.ecart_signe) > 0 ? '+' : '−';
        const abs = Math.abs(parseFloat(ax.ecart_signe));
        if (ax.champ === 'quantite') {
          label = 'Écart de quantité';
          morceaux.push(`${DOCTAG[t]} : <b>${fmtQty(ax.valeurComparee)}</b> sur <b>${fmtQty(ax.valeurReference)}</b> (${signe}${fmtQty(String(abs))})`);
        } else if (ax.champ === 'prixUnitaireHT') {
          label = 'Écart de prix';
          morceaux.push(`${DOCTAG[t]} <b>${signe}${fmtMoney(abs)}</b>/u`);
        } else if (ax.champ === 'montantHT') {
          if (label === 'Écart') label = 'Écart de montant';
          morceaux.push(`${DOCTAG[t]} montant <b>${signe}${fmtMoney(abs)}</b>`);
        } else if (ax.champ === 'tauxRemise') {
          if (label === 'Écart') label = 'Écart de remise';
          morceaux.push(`${DOCTAG[t]} remise différente`);
        }
      }
    }
    return { cls: 'v-err', badge: 'b-err', label,
             small: morceaux.join(' · ') || 'Écart détecté' };
  }
  return { cls: 'v-warn', badge: 'b-mut', label: 'Non comparable',
           small: 'Valeurs absentes d\u2019un des documents' };
}

function ambForProduct(c, p) {
  const i = parseInt(p.cle.split(':')[1], 10);
  return (c.ambiguites || []).filter(a => a.reference_index === i
                                       && a.paire.startsWith('BC↔'));
}

function correctedSet(t) {
  return new Set(Object.keys(revState.corrections[t] || {}).map(Number));
}

function renderLedger(a, c) {
  const produits = (c.produits || []).filter(isLedgerProduct);
  if (!produits.length) return '';
  let html = `
    <div id="ledger">
      <div class="lhead">
        <div>Doc</div><div>Référence</div><div>Désignation</div>
        <div class="r">Qté</div><div>Unité</div><div class="r">PU HT</div><div class="r">Remise (%)</div><div class="r">Total HT</div>
        <div style="text-align:center">Résultat</div>
      </div>`;
  for (const p of produits) {
    const v = verdictOf(p);
    const bad = ecartAxes(p);
    const bcOrigin = (p.lignes.BC?.lignes_source || [])[0];
    let rows = '';
    for (const t of ['BC', 'Facture', 'BL']) {
      const l = p.lignes[t];
      if (l) {
        rows += lineCells(t, l, bad[t],
          (l.lignes_source || []).some(i => correctedSet(t).has(i)));
        continue;
      }
      if (t === 'BC') continue;
      const paire = (p.paires || {})[PAIRE[t]];
      if (!paire) continue;
      if (paire.statut === 'manquant') {
        rows += `<div class="lrow ghost miss">
          <div><span class="doctag">${DOCTAG[t]}</span></div>
          <div class="glabel">${t === 'BL' ? 'Non livré' : 'Non facturé'}</div>
          <div class="des"><span>Aucune ligne rapprochée</span></div>
          <div class="num">·</div><div class="unitc">·</div><div class="num">·</div><div class="num">·</div><div class="num">·</div></div>`;
      } else if (paire.statut === 'ambigu') {
        const nb = (paire.candidats || []).length;
        rows += `<div class="lrow ghost amb" data-cle="${esc(p.cle)}" data-t="${t}">
          <div><span class="doctag">${DOCTAG[t]}</span></div>
          <div class="glabel">Ambigu</div>
          <div class="des"><span>${nb} candidat(s) possible(s) — cliquer pour trancher</span></div>
          <div class="num">·</div><div class="unitc">·</div><div class="num">·</div><div class="num">·</div><div class="num">·</div></div>`;
      }
    }
    html += `
      <div class="grp ${v.cls}" data-cle="${esc(p.cle)}" data-bc="${bcOrigin ?? ''}">
        <div class="rows">${rows}</div>
        <div class="verdict">
          <span class="badge ${v.badge} status"><span class="dot"></span>${v.label}</span>
          <small>${v.small}</small>
        </div>
      </div>`;
  }
  return html + '</div>';
}

/* ---------- non rapprochées ---------- */

function renderLoose(a, c) {
  const items = [];

  for (const p of (c.produits || [])) {
    if (p.cle.startsWith('BC:') && !isLedgerProduct(p)) {
      const l = p.lignes.BC;
      const cibles = Object.keys(p.paires || {});
      const motifs = cibles.map(k => k === 'BC↔BL' ? 'Non livré' : 'Non facturé');
      items.push({ t: 'BC', l, badge: 'b-err', motif: motifs.join(' · ') });
    }
    if (p.cle.startsWith('HORS_BC:')) {
      for (const [t, l] of Object.entries(p.lignes)) {
        const paire = (p.paires || {})[PAIRE[t]] || {};
        const det = (paire.message || '').includes('détachée');
        items.push({ t, l, badge: det ? 'b-edit' : 'b-err',
                     motif: det ? 'Détachée par l\u2019opérateur' : 'En trop' });
      }
    }
  }
  for (const amb of (c.ambiguites || [])) {
    if (!amb.paire.startsWith('BC↔')) continue;
    const t = amb.paire.split('↔')[1];
    for (const cand of amb.candidats || []) {
      items.push({ t, l: cand, badge: 'b-warn',
                   motif: `Ambigu · candidat ${esc(amb.reference || 'BC:' + amb.reference_index)}`,
                   affect: { bc: (amb.lignes_source || [])[0], t,
                             srcs: cand.lignes_source || [] } });
    }
  }

  let html = `
    <div class="loose" id="loose">
      <h3>Lignes non rapprochées</h3>
      <div class="grp1"><div class="rows" id="looseRows">`;
  /* Une même ligne d'origine peut être signalée plusieurs fois (en trop ET
   * candidate d'une ambiguïté, ou candidate de deux ambiguïtés) : elle n'est
   * affichée qu'une fois. À doublon, l'entrée actionnable (Affecter) prime. */
  const seen = new Map();
  for (const it of items) {
    const key = it.t + ':' + (it.l.lignes_source || []).join(',');
    const prev = seen.get(key);
    if (!prev || (!prev.affect && it.affect)) seen.set(key, it);
  }
  const uniques = [...seen.values()];

  if (!uniques.length)
    html += '<div class="empty">Toutes les lignes sont rapprochées.</div>';
  for (const it of uniques) {
    const l = it.l;
    const draggable = (l.lignes_source || []).length;
    const bcTarget = it.t === 'BC'
      ? ` data-bc="${(l.lignes_source || [])[0] ?? ''}"` : '';
    html += `
      <div class="lrow" data-doc="${DOCTAG[it.t]}" data-type="${it.t}"
           ${draggable ? 'draggable="true"' : ''}${bcTarget}
           data-src="${(l.lignes_source || []).join(',')}">
        <div><span class="doctag">${DOCTAG[it.t]}</span></div>
        <div class="ref">${esc(l.reference || '—')}</div>
        <div class="des"><span>${esc(l.designation || '—')}</span></div>
        <div class="num">${fmtQty(l.quantite)}</div>
        <div class="unitc">${esc(l.unite || '—')}</div>
        <div class="num">${fmtMoney(l.prixUnitaireHT)}</div>
        <div class="num">${fmtRem(l.tauxRemise)}</div>
        <div class="num">${fmtMoney(l.montantHT)}</div>
        <div class="motif"><span class="badge ${it.badge}"><span class="dot"></span>${it.motif}</span>
          ${it.affect ? `<button class="btn cand-affect" data-bc="${it.affect.bc}"
              data-t="${it.affect.t}" data-srcs="${it.affect.srcs.join(',')}">Affecter</button>` : ''}
        </div>
      </div>`;
  }
  return html + '</div></div></div>';
}

/* ---------- synthèse des montants ---------- */

function totalOf(d) {
  const t = d?.totaux || {};
  return t.netHT ?? t.totalHT ?? null;
}

/* Champs de totaux affichés, dans l'ordre du document : chaque ligne du
 * tableau est un champ, chaque colonne un document présent. */
const TOTAUX_CHAMPS = [
  ['totalHT',      'Total HT',      'money'],
  ['remiseTotale', 'Remise totale', 'money'],
  ['netHT',        'Net HT',        'money'],
  ['tauxTVA',      'Taux TVA (%)',  'rate'],
  ['montantTVA',   'Montant TVA',   'money'],
  ['timbreFiscal', 'Timbre fiscal', 'money'],
  ['totalTTC',     'Total TTC',     'money'],
  ['netAPayer',    'Net à payer',   'money'],
];

/* Contrôle croisé d'un champ de totaux entre documents. Le BC fait référence
 * quand il porte le champ ; la tolérance est dérivée de la précision
 * d'affichage la plus grossière des valeurs comparées (jamais une constante),
 * avec un plancher relatif de 0,05 % sur les montants — mêmes règles que L8. */
function decCount(v) {
  const s = String(v);
  const i = s.indexOf('.');
  return i < 0 ? 0 : s.length - i - 1;
}
function checkTotal(cle, kind, docs) {
  const vals = docs
    .map(({ t, d }) => ({ t, raw: (d.totaux || {})[cle] }))
    .filter(x => x.raw != null && String(x.raw).trim() !== '');
  if (vals.length < 2)
    return { css: 'b-mut', label: 'Non comparé' };
  const ref = vals.find(x => x.t === 'BC') || vals[0];
  const refN = parseFloat(ref.raw);
  const quantum = Math.pow(10, -Math.min(...vals.map(x => decCount(x.raw))));
  const tol = kind === 'rate' ? quantum
            : Math.max(quantum, Math.abs(refN) * 0.0005);
  let worst = 0;
  for (const x of vals) {
    if (x === ref) continue;
    const delta = parseFloat(x.raw) - refN;
    if (Math.abs(delta) > tol && Math.abs(delta) > Math.abs(worst)) worst = delta;
  }
  if (worst === 0) return { css: 'b-ok', label: 'Conforme' };
  const signe = worst > 0 ? '+' : '−';
  const abs = kind === 'rate' ? fmtRem(Math.abs(worst).toFixed(4))
                              : fmtMoney(String(Math.abs(worst)));
  return { css: 'b-err', label: `Écart ${signe}${abs}` };
}

function renderSums(a, c) {
  const docs = ['BC', 'BL', 'Facture']
    .map(t => ({ t, d: docByType(t) }))
    .filter(x => x.d);
  if (!docs.length) return '';

  // Écart net facturé / commandé (lignes rapprochées) — conservé en pied
  const fa = docByType('Facture');
  let deltaFA = 0, nonFacture = 0;
  if (fa) {
    for (const p of c.produits || []) {
      const paire = (p.paires || {})['BC↔Facture'];
      if (!paire) continue;
      if (paire.statut === 'manquant')
        nonFacture += parseFloat(p.lignes.BC?.montantHT) || 0;
      for (const ax of paire.axes || [])
        if (ax.champ === 'montantHT' && ax.statut === 'écart')
          deltaFA += parseFloat(ax.ecart_signe) || 0;
    }
  }

  const devise = (docByType('BC')?.devise) ||
    (analysis.documents_detail || []).map(d => d.devise).find(Boolean) || '';

  let html = `
    <div class="sums"><h3>Synthèse des montants${devise ? ` <span class="dev">(${esc(devise)})</span>` : ''}</h3>
    <table class="sumtbl">
      <thead><tr><th>Champ</th>`;
  for (const { t, d } of docs) {
    const nb = c.documents?.[t]?.lignes;
    html += `<th class="r">${DOCLABEL[t]}
      <small>${esc(d.numero || '—')} · ${fmtDate(d.date)}${nb != null ? ` · ${nb} ligne${nb > 1 ? 's' : ''}` : ''}</small></th>`;
  }
  html += `<th class="ctr">Résultat</th></tr></thead><tbody>`;

  for (const [cle, label, kind] of TOTAUX_CHAMPS) {
    // une ligne n'est affichée que si au moins un document porte le champ
    if (!docs.some(({ d }) => (d.totaux || {})[cle] != null)) continue;
    html += `<tr><td class="champ">${label}</td>`;
    for (const { d } of docs) {
      const v = (d.totaux || {})[cle];
      html += `<td class="r num">${v == null ? '—'
        : kind === 'rate' ? fmtRem(v) : fmtMoney(v)}</td>`;
    }
    const chk = checkTotal(cle, kind, docs);
    html += `<td class="ctr"><span class="badge ${chk.css}"><span class="dot"></span>${chk.label}</span></td></tr>`;
  }

  if (fa) {
    const bits = [];
    if (deltaFA) bits.push(deltaFA > 0 ? 'surfacturation' : 'sous-facturation');
    if (nonFacture) bits.push(fmtMoney(nonFacture) + ' non facturé');
    html += `
    <tr class="tot"><td colspan="${docs.length + 1}">Écart net facturé / commandé (lignes rapprochées)${bits.length ? ` — ${bits.join(' · ')}` : ''}</td>
      <td class="r num ${deltaFA ? 'pos' : ''}">${deltaFA ? (deltaFA > 0 ? '+' : '−') + fmtMoney(Math.abs(deltaFA)) + (devise ? ' ' + esc(devise) : '') : '—'}</td></tr>`;
  }
  return html + '</tbody></table></div>';
}

/* ==================== Gestes de révision (BF9) =================== */

function markGrp(g) {
  if (!g) return;
  g.classList.add('edited');
  const b = g.querySelector('.status');
  if (b) { b.className = 'badge b-edit status';
           b.innerHTML = '<span class="dot"></span>Révisé — en attente'; }
  const sm = g.querySelector('.verdict small');
  if (sm) sm.textContent = 'Recalcul à l\u2019enregistrement';
}

function paireOf(type) { return PAIRE[type]; }

function rapp(paire) {
  const r = revState.rapprochements;
  r[paire] = r[paire] || {};
  r[paire].affectations = r[paire].affectations || {};
  r[paire].detachees = r[paire].detachees || [];
  return r[paire];
}

function retirerPartout(paire, srcs) {
  /* une ligne réaffectée quitte ses affectations et détachements antérieurs */
  const spec = rapp(paire);
  for (const [bc, list] of Object.entries(spec.affectations)) {
    spec.affectations[bc] = list.filter(j => !srcs.includes(j));
    if (!spec.affectations[bc].length) delete spec.affectations[bc];
  }
  spec.detachees = spec.detachees.filter(j => !srcs.includes(j));
}

function affecter(type, srcs, bcOrigin) {
  const paire = paireOf(type);
  if (!paire || bcOrigin === '' || bcOrigin == null)
    return toast('Affectation impossible sur ce groupe', false);
  retirerPartout(paire, srcs);
  const spec = rapp(paire);
  const key = String(bcOrigin);
  const list = spec.affectations[key] || [];
  for (const j of srcs) if (!list.includes(j)) list.push(j);
  spec.affectations[key] = list.sort((a, b) => a - b);
  pendingOps++; updateApplybar();
}

function detacher(type, srcs) {
  const paire = paireOf(type);
  if (!paire) return;
  retirerPartout(paire, srcs);
  const spec = rapp(paire);
  for (const j of srcs) if (!spec.detachees.includes(j)) spec.detachees.push(j);
  spec.detachees.sort((a, b) => a - b);
  pendingOps++; updateApplybar();
}

function corriger(type, origin, champ, valeur) {
  const c = revState.corrections;
  c[type] = c[type] || {};
  c[type][String(origin)] = c[type][String(origin)] || {};
  c[type][String(origin)][champ] = valeur;
  pendingOps++; updateApplybar();
}

/* ---------- interactions du DOM ---------- */

const CHAMP_RAW = { quantite: true, prixUnitaireHT: true, tauxRemise: true,
                    montantHT: true, reference: true, designation: true,
                    unite: true };

let dragged = null;   // ligne en cours de glisser (état partagé des vues)

document.addEventListener('dragover', e => {
  if (!dragged) return;

  // Défilement automatique : approcher le curseur du bord haut ou bas de la
  // fenêtre fait défiler la page, permettant de déposer une ligne du bas du
  // registre sur un groupe tout en haut (et inversement).
  const MARGE = 80, PAS = 22;
  if (e.clientY < MARGE) window.scrollBy(0, -PAS);
  else if (window.innerHeight - e.clientY < MARGE) window.scrollBy(0, PAS);

  $$('.gover').forEach(x => x.classList.remove('gover'));
  $('#loose')?.classList.remove('lover');

  // Ligne BC glissée : les cibles sont les lignes FA/BL non rapprochées —
  // le dépôt attache la ligne cible à ce produit du BC (même opération
  // qu'un glissement dans l'autre sens).
  if (dragged.dataset.type === 'BC') {
    const r = e.target.closest('#looseRows .lrow');
    if (r && r !== dragged && r.dataset.type !== 'BC' && r.dataset.src) {
      e.preventDefault(); r.classList.add('gover');
    }
    return;
  }

  const g = e.target.closest('#ledger .grp');
  const bcRow = e.target.closest('#looseRows .lrow[data-type="BC"]');
  const lz = e.target.closest('#loose');
  if (g && !g.contains(dragged)) { e.preventDefault(); g.classList.add('gover'); }
  else if (bcRow) { e.preventDefault(); bcRow.classList.add('gover'); }
  else if (lz && !lz.contains(dragged)) { e.preventDefault(); $('#loose').classList.add('lover'); }
});

document.addEventListener('drop', e => {
  if (!dragged) return;
  const srcs = (dragged.dataset.src || '').split(',').filter(x => x !== '')
                .map(Number);
  const type = dragged.dataset.type;

  // Dépôt d'une ligne BC sur une ligne FA/BL non rapprochée : la ligne
  // cible est affectée au produit du BC glissé.
  if (type === 'BC') {
    const r = e.target.closest('#looseRows .lrow');
    if (!r || r === dragged || r.dataset.type === 'BC' || !r.dataset.src) return;
    e.preventDefault();
    const tsrcs = r.dataset.src.split(',').filter(x => x !== '').map(Number);
    affecter(r.dataset.type, tsrcs, srcs[0]);
    const g0 = dragged.closest('.grp');
    if (g0) {
      markGrp(g0);
      const motif = r.querySelector('.motif');
      if (motif) motif.remove();
      r.classList.add('row-pending');
      const des = r.querySelector('.des');
      if (des && !des.querySelector('.pend'))
        des.insertAdjacentHTML('beforeend',
          '<span class="fuz pend" title="Réaffectée par l\u2019opérateur — ' +
          'comparaison recalculée à l\u2019enregistrement">→ affectée, en attente</span>');
      g0.querySelector('.rows').appendChild(r);
    } else {
      // BC lui-même non rapproché : aperçu minimal, l'état vrai revient du serveur
      r.classList.add('row-pending');
      const m = r.querySelector('.motif');
      if (m) m.innerHTML = '<span class="badge b-edit"><span class="dot"></span>Affectée — en attente</span>';
      dragged.after(r);
    }
    return;
  }

  const g = e.target.closest('#ledger .grp');
  const bcRow = e.target.closest('#looseRows .lrow[data-type="BC"]');
  const lz = e.target.closest('#loose');
  if (bcRow && bcRow.dataset.bc !== '') {
    e.preventDefault();
    affecter(type, srcs, bcRow.dataset.bc);
    dragged.classList.add('row-pending');
    const m = dragged.querySelector('.motif');
    if (m) m.innerHTML = '<span class="badge b-edit"><span class="dot"></span>Affectée — en attente</span>';
    markGrp(dragged.closest('.grp'));
    bcRow.after(dragged);
    return;
  }
  if (g && !g.contains(dragged)) {
    e.preventDefault();
    affecter(type, srcs, g.dataset.bc);
    markGrp(g); markGrp(dragged.closest('.grp'));
    // Aperçu : la ligne réelle est DÉPLACÉE avec toutes ses données
    // (référence, quantité, remise…) ; seul le résultat de comparaison
    // sera recalculé à l'enregistrement — l'état vrai revient du serveur.
    const motif = dragged.querySelector('.motif');
    if (motif) motif.remove();      // colonne motif des non rapprochées
    dragged.classList.add('row-pending');
    const des = dragged.querySelector('.des');
    if (des && !des.querySelector('.pend'))
      des.insertAdjacentHTML('beforeend',
        '<span class="fuz pend" title="Réaffectée par l\u2019opérateur — ' +
        'comparaison recalculée à l\u2019enregistrement">→ affectée, en attente</span>');
    g.querySelector('.rows').appendChild(dragged);
  } else if (lz && !lz.contains(dragged)) {
    e.preventDefault();
    detacher(type, srcs);
    markGrp(dragged.closest('.grp'));
    const m = dragged.querySelector('.motif');
    if (m) m.innerHTML = '<span class="badge b-edit"><span class="dot"></span>Détachée — en attente</span>';
    else dragged.insertAdjacentHTML('beforeend',
      '<div class="motif"><span class="badge b-edit"><span class="dot"></span>Détachée — en attente</span></div>');
    $('#looseRows').appendChild(dragged);
  }
});

/* Règles de saisie par champ — appliquées EN TEMPS RÉEL (les caractères
 * invalides sont refusés à la frappe) puis revalidées à la validation de la
 * cellule. Le serveur revérifie (422) : le client n'est qu'un premier filtre. */
const CHAMP_REGLES = {
  quantite:       { live: /^\d*$/,               ok: /^\d+$/,
                    msg: 'Quantité : entier positif attendu' },
  prixUnitaireHT: { live: /^\d*[.,]?\d*$/,       ok: /^\d+([.,]\d+)?$/,
                    msg: 'Prix unitaire : nombre positif attendu' },
  montantHT:      { live: /^\d*[.,]?\d*$/,       ok: /^\d+([.,]\d+)?$/,
                    msg: 'Montant : nombre positif attendu' },
  tauxRemise:     { live: /^\d*[.,]?\d*$/,       ok: /^\d+([.,]\d+)?$/,
                    msg: 'Remise : nombre entre 0 et 100 attendu',
                    borne: v => parseFloat(v.replace(',', '.')) <= 100 },
};

function afficherCellule(cell, champ, v) {
  /* Réaffiche la cellule selon le contrat d'affichage après édition. */
  if (v === '') { cell.textContent = '—'; return; }
  if (champ === 'quantite') {
    cell.textContent = fmtQty(v);
  } else if (champ === 'prixUnitaireHT' || champ === 'montantHT') {
    cell.textContent = fmtMoney(v);
  } else if (champ === 'tauxRemise') {
    cell.textContent = fmtRem(v);
  } else {
    cell.textContent = v;
  }
}

function bindResultEvents() {
  // Édition de valeur au double-clic — la saisie est une chaîne brute,
  // renvoyée telle quelle : L6/L7 normalisent et revalident côté serveur.
  $$('#resBody .val').forEach(cell => cell.addEventListener('dblclick', () => {
    if (cell.querySelector('input')) return;
    const champ = cell.dataset.f;
    if (!CHAMP_RAW[champ]) return;
    const regles = CHAMP_REGLES[champ];
    const old = cell.dataset.v ?? '';
    const oldHTML = cell.innerHTML;
    cell.innerHTML = `<input value="${esc(old)}">`;
    const inp = cell.querySelector('input');
    inp.focus(); inp.select();

    // Filtre à la frappe : tout caractère hors motif est refusé immédiatement.
    if (regles) {
      let dernier = inp.value;
      inp.addEventListener('input', () => {
        if (regles.live.test(inp.value)) dernier = inp.value;
        else inp.value = dernier;
      });
    }

    let done = false;
    const commit = () => {
      if (done) return; done = true;
      const v = inp.value.trim();
      if (v && regles && (!regles.ok.test(v) ||
                          (regles.borne && !regles.borne(v)))) {
        cell.innerHTML = oldHTML;          // valeur invalide : rien n'est envoyé
        cell.classList.add('cell-invalid');
        setTimeout(() => cell.classList.remove('cell-invalid'), 1600);
        toast(regles.msg, false);
        return;
      }
      afficherCellule(cell, champ, v);
      cell.dataset.v = v;
      if (v !== old) {
        cell.classList.add('cell-edit');
        corriger(cell.dataset.doc, cell.dataset.i, champ, v);
        markGrp(cell.closest('.grp'));
        const row = cell.closest('.lrow');
        if (row && !cell.closest('.grp')) row.classList.add('row-touched');
      }
    };
    inp.addEventListener('blur', commit);
    inp.addEventListener('keydown', ev => {
      if (ev.key === 'Enter') inp.blur();
      if (ev.key === 'Escape') { done = true; cell.innerHTML = oldHTML; }
    });
  }));

  // Glisser-déposer : réaffecter une ligne BL/FA à un autre produit du BC,
  // ou la détacher vers les non rapprochées. Les écouteurs au niveau du
  // document sont enregistrés une seule fois (voir plus bas) ; ici, seuls
  // les écouteurs par ligne, recréés à chaque rendu.
  $$('#resBody .lrow[draggable="true"]').forEach(r => {
    r.addEventListener('dragstart', e => {
      dragged = r; r.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
    });
    r.addEventListener('dragend', () => {
      r.classList.remove('dragging');
      $$('.gover').forEach(x => x.classList.remove('gover'));
      $('#loose')?.classList.remove('lover');
      dragged = null;
    });
  });

  // Ambiguïtés : clic sur la ligne fantôme -> liste des candidats
  $$('#resBody .ghost.amb').forEach(gh => gh.addEventListener('click', () => {
    const grp = gh.closest('.grp');
    if (grp.querySelector('.cands')) { grp.querySelector('.cands').remove(); return; }
    const p = analysis.comparaison.produits.find(x => x.cle === grp.dataset.cle);
    const t = gh.dataset.t;
    const paire = (p.paires || {})[PAIRE[t]] || {};
    const bc = grp.dataset.bc;
    const cands = (paire.candidats || []).map(cd => `
      <div class="cand">
        <span class="ref">${esc(cd.reference || '—')}</span>
        <span>${esc(cd.designation || '—')}</span>
        <span class="num">${fmtQty(cd.quantite)}</span>
        <span class="num">${fmtMoney(cd.prixUnitaireHT)}</span>
        <button class="btn cand-affect" data-bc="${bc}" data-t="${t}"
                data-srcs="${(cd.lignes_source || []).join(',')}">Choisir</button>
      </div>`).join('');
    grp.querySelector('.rows').insertAdjacentHTML('beforeend',
      `<div class="cands"><span class="cttl">${esc(paire.motif || 'Candidats')}</span>${cands}</div>`);
    bindAffectButtons();
  }));

  bindAffectButtons();

  // Pied de page
  $('#btnRapport')?.addEventListener('click', downloadRapport);
  $('#btnReplay')?.addEventListener('click', async () => {
    await saveRevisions(revState, 'Analyse rejouée à l\u2019identique');
  });
}

function bindAffectButtons() {
  $$('.cand-affect').forEach(b => {
    if (b.dataset.bound) return;
    b.dataset.bound = '1';
    b.addEventListener('click', e => {
      e.stopPropagation();
      const srcs = (b.dataset.srcs || '').split(',').filter(x => x !== '')
                    .map(Number);
      affecter(b.dataset.t, srcs, b.dataset.bc);
      const grp = b.closest('.grp');
      if (grp) markGrp(grp);
      b.closest('.cand, .lrow')?.classList.add('row-touched');
      b.textContent = 'Choisi ✓'; b.disabled = true;
      toast('Affectation enregistrée — appliquer pour recalculer');
    });
  });
}

/* ---------- application / annulation ---------- */

$('#btnCancel').addEventListener('click', () => {
  freshRevState();
  renderResults();
  toast('Révisions annulées');
});

$('#btnApply').addEventListener('click', () => saveRevisions(
  revState, 'Comparaison recalculée — rapport PDF régénéré'));

async function saveRevisions(payload, okMsg) {
  if (!analysis) return;
  $('#recalc').classList.add('on');
  try {
    analysis = await api(`/api/analyses/${analysis.id}/revisions`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    freshRevState();
    renderResults();
    toast(okMsg);
  } catch (e) {
    toast(e.message, false);
  } finally {
    $('#recalc').classList.remove('on');
  }
}

async function downloadRapport() {
  try {
    const res = await fetch(`/api/analyses/${analysis.id}/rapport`,
      { headers: { Authorization: 'Bearer ' + token } });
    if (!res.ok) throw new Error('Rapport indisponible');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `rapport_${analysis.fichier.replace(/\.pdf$/i, '')}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
    toast('Rapport PDF téléchargé');
  } catch (e) { toast(e.message, false); }
}

/* ============================== Boot ============================= */

boot();
