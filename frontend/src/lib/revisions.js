/* Révisions de l'opérateur — même format que l'ancienne interface et que
 * PATCH /api/analyses/{id}/revisions (voir docs/api.md) :
 *
 *   {
 *     "corrections":    { "BL": { "3": { "quantite": "60" } } },
 *     "rapprochements": { "BC↔BL": { "affectations": { "0": [2, 4] }, "detachees": [5] } }
 *   }
 *
 * Les index sont ceux des lignes d'origine (0, 1, 2…). Le corps envoyé est
 * l'état COMPLET : on part des révisions déjà enregistrées et on rejoue
 * par-dessus la liste des gestes en attente. Retirer un geste = le retirer de
 * la liste et rejouer. */

import { DOC, FIELD_LABEL, PAIR_OF } from './status.js';

export function baseRevisions(analysis) {
  const r = analysis?.revisions ? structuredClone(analysis.revisions) : {};
  r.corrections = r.corrections || {};
  r.rapprochements = r.rapprochements || {};
  return r;
}

function spec(state, pair) {
  const r = state.rapprochements;
  r[pair] = r[pair] || {};
  r[pair].affectations = r[pair].affectations || {};
  r[pair].detachees = r[pair].detachees || [];
  return r[pair];
}

/* Une ligne réaffectée quitte ses affectations et détachements antérieurs. */
function removeEverywhere(s, srcs) {
  for (const [bc, list] of Object.entries(s.affectations)) {
    s.affectations[bc] = list.filter((j) => !srcs.includes(j));
    if (!s.affectations[bc].length) delete s.affectations[bc];
  }
  s.detachees = s.detachees.filter((j) => !srcs.includes(j));
}

function applyOp(state, op) {
  if (op.kind === 'assign') {
    const s = spec(state, PAIR_OF[op.doc]);
    removeEverywhere(s, op.srcs);
    const key = String(op.bc);
    const list = s.affectations[key] || [];
    for (const j of op.srcs) if (!list.includes(j)) list.push(j);
    s.affectations[key] = list.sort((a, b) => a - b);
  } else if (op.kind === 'detach') {
    const s = spec(state, PAIR_OF[op.doc]);
    removeEverywhere(s, op.srcs);
    for (const j of op.srcs) if (!s.detachees.includes(j)) s.detachees.push(j);
    s.detachees.sort((a, b) => a - b);
  } else if (op.kind === 'correct') {
    const c = state.corrections;
    c[op.doc] = c[op.doc] || {};
    c[op.doc][String(op.origin)] = { ...(c[op.doc][String(op.origin)] || {}), ...op.fields };
  }
}

function cleanup(state) {
  for (const [pair, s] of Object.entries(state.rapprochements)) {
    const empty = !Object.keys(s.affectations || {}).length && !(s.detachees || []).length;
    if (empty) delete state.rapprochements[pair];
  }
  return state;
}

export function replay(analysis, ops) {
  const state = baseRevisions(analysis);
  for (const op of ops) applyOp(state, op);
  return cleanup(state);
}

/* Lignes touchées par les gestes en attente : "BL:3" etc. */
export function touchedLines(ops) {
  const out = new Set();
  for (const op of ops) {
    if (op.kind === 'correct') out.add(`${op.doc}:${op.origin}`);
    else for (const j of op.srcs) out.add(`${op.doc}:${j}`);
  }
  return out;
}

export function describeOp(op) {
  const tag = DOC[op.doc]?.tag || op.doc;
  const lines = (srcs) => srcs.map((j) => j + 1).join(', ');
  if (op.kind === 'assign') {
    return `${tag} ligne${op.srcs.length > 1 ? 's' : ''} ${lines(op.srcs)} → affectée${op.srcs.length > 1 ? 's' : ''} à BC ligne ${op.bc + 1}`;
  }
  if (op.kind === 'detach') {
    return `${tag} ligne${op.srcs.length > 1 ? 's' : ''} ${lines(op.srcs)} → détachée${op.srcs.length > 1 ? 's' : ''}`;
  }
  const fields = Object.entries(op.fields)
    .map(([f, v]) => `${FIELD_LABEL[f] || f} = ${v === '' ? '(vide)' : v}`)
    .join(', ');
  return `${tag} ligne ${op.origin + 1} corrigée : ${fields}`;
}

/* Révisions déjà enregistrées, en phrases (piste d'audit). */
export function describeSaved(revisions) {
  const out = [];
  for (const [doc, byLine] of Object.entries(revisions?.corrections || {})) {
    for (const [origin, fields] of Object.entries(byLine || {})) {
      out.push({ kind: 'correct', text: describeOp({ kind: 'correct', doc, origin: Number(origin), fields }) });
    }
  }
  for (const [pair, s] of Object.entries(revisions?.rapprochements || {})) {
    const doc = pair.split('↔')[1];
    for (const [bc, srcs] of Object.entries(s?.affectations || {})) {
      out.push({ kind: 'assign', text: describeOp({ kind: 'assign', doc, srcs, bc: Number(bc) }) });
    }
    if ((s?.detachees || []).length) {
      out.push({ kind: 'detach', text: describeOp({ kind: 'detach', doc, srcs: s.detachees }) });
    }
  }
  return out;
}

/* Règles de saisie, identiques au contrôle serveur (422 sinon). */
export const FIELD_RULES = {
  quantite: { ok: /^\d+$/, msg: 'Quantité : nombre entier positif attendu' },
  prixUnitaireHT: { ok: /^\d+([.,]\d+)?$/, msg: 'Prix unitaire : nombre positif attendu' },
  montantHT: { ok: /^\d+([.,]\d+)?$/, msg: 'Montant : nombre positif attendu' },
  tauxRemise: {
    ok: /^\d+([.,]\d+)?$/,
    msg: 'Remise : nombre entre 0 et 100 attendu',
    bound: (v) => parseFloat(v.replace(',', '.')) <= 100,
  },
};

export const EDITABLE_FIELDS = [
  'reference',
  'designation',
  'unite',
  'quantite',
  'prixUnitaireHT',
  'tauxRemise',
  'montantHT',
];

export function validateField(field, value) {
  const v = String(value ?? '').trim();
  if (!v) return null;
  const rule = FIELD_RULES[field];
  if (!rule) return null;
  if (!rule.ok.test(v) || (rule.bound && !rule.bound(v))) return rule.msg;
  return null;
}
