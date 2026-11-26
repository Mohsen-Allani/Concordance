/* Lecture du résultat de comparaison L8 (analyse.comparaison).
 *
 * Rien n'est recalculé ici : ces fonctions réorganisent pour l'affichage ce
 * que le moteur a produit. La seule exception est le contrôle croisé des
 * totaux (`checkTotal`), repris tel quel de l'ancienne interface. */

import { DOC, PAIR_OF, TARGET_TYPES } from './status.js';
import { fmtMoney, fmtQty, fmtRate } from './format.js';

export const isBcProduct = (p) => p.cle?.startsWith('BC:');
export const isOutsideBc = (p) => p.cle?.startsWith('HORS_BC:');

export const lineNo = (origin) => (origin === null || origin === undefined ? '—' : origin + 1);
export const originsOf = (line) => line?.lignes_source || [];
export const lineKey = (type, origins) => `${type}:${origins.join(',')}`;

export function docByType(analysis, type) {
  return (analysis?.documents_detail || []).find((d) => d.type === type);
}

export function presentTargets(comparison) {
  return TARGET_TYPES.filter((t) => comparison?.documents?.[t]);
}

/* Un produit du BC est « rapproché » s'il a au moins une contrepartie. */
export function isMatchedProduct(p) {
  if (!isBcProduct(p)) return false;
  const pairs = Object.values(p.paires || {});
  return !(pairs.length && pairs.every((x) => x.statut === 'manquant'));
}

/* Champs en écart par document cible : { BL: Set, Facture: Set }. */
export function gapFields(p) {
  const out = { BC: new Set(), BL: new Set(), Facture: new Set() };
  for (const t of TARGET_TYPES) {
    for (const ax of p.paires?.[PAIR_OF[t]]?.axes || []) {
      if (ax.statut === 'écart') {
        out[t].add(ax.champ);
        out.BC.add(ax.champ);
      }
    }
  }
  return out;
}

/* Résumé lisible d'un produit : titre + détails (texte brut). */
export function productSummary(p) {
  const s = p.statut;
  if (s === 'conforme') return { title: 'Conforme', details: ['Quantités et prix concordants'] };
  if (s === 'non_comparable') {
    return { title: 'Non comparable', details: ["Valeurs absentes de l'un des documents"] };
  }
  if (s === 'ambigu') {
    const n = Object.values(p.paires || {}).filter((x) => x.statut === 'ambigu').length;
    return {
      title: 'Rapprochement à trancher',
      details: [n > 1 ? 'Deux rapprochements non tranchés' : 'Plusieurs lignes candidates'],
    };
  }
  if (s === 'en_trop') {
    const details = Object.keys(p.lignes || {}).map((t) => {
      const msg = p.paires?.[PAIR_OF[t]]?.message || '';
      return msg.includes('détachée')
        ? `${DOC[t].tag} : détachée par l'opérateur`
        : `${DOC[t].tag} : présente, absente du BC`;
    });
    return { title: 'Hors commande', details };
  }

  const details = [];
  let title = 'Écart';
  for (const t of TARGET_TYPES) {
    const pair = p.paires?.[PAIR_OF[t]];
    if (!pair) continue;
    if (pair.statut === 'manquant') {
      details.push(t === 'BL' ? 'Non livré' : 'Non facturé');
      if (title === 'Écart') title = t === 'BL' ? 'Non livré' : 'Non facturé';
      continue;
    }
    for (const ax of pair.axes || []) {
      if (ax.statut !== 'écart') continue;
      const n = parseFloat(ax.ecart_signe);
      const sign = n > 0 ? '+' : '−';
      const abs = Math.abs(n);
      const tag = DOC[t].tag;
      if (ax.champ === 'quantite') {
        title = 'Écart de quantité';
        details.push(
          `${tag} : ${fmtQty(ax.valeurComparee)} sur ${fmtQty(ax.valeurReference)} (${sign}${fmtQty(String(abs))})`,
        );
      } else if (ax.champ === 'prixUnitaireHT') {
        title = 'Écart de prix';
        details.push(`${tag} : ${sign}${fmtMoney(abs)} par unité`);
      } else if (ax.champ === 'montantHT') {
        if (title === 'Écart') title = 'Écart de montant';
        details.push(`${tag} : montant ${sign}${fmtMoney(abs)}`);
      } else if (ax.champ === 'tauxRemise') {
        if (title === 'Écart') title = 'Écart de remise';
        details.push(`${tag} : remise ${fmtRate(ax.valeurComparee)} % au lieu de ${fmtRate(ax.valeurReference)} %`);
      }
    }
  }
  return { title, details: details.length ? details : ['Écart détecté'] };
}

export function statusCounts(produits = []) {
  const out = { conforme: 0, 'écart': 0, manquant: 0, en_trop: 0, ambigu: 0, non_comparable: 0 };
  for (const p of produits) if (p.statut in out) out[p.statut] += 1;
  return out;
}

/* Lignes du BC, pour les listes « affecter à… ». */
export function bcLineOptions(comparison) {
  return (comparison?.produits || [])
    .filter(isBcProduct)
    .map((p) => {
      const l = p.lignes.BC;
      const origins = originsOf(l);
      return {
        origin: origins[0],
        origins,
        line: l,
        statut: p.statut,
        label: `BC · ligne ${lineNo(origins[0])} — ${l.reference || 'sans réf.'} · ${l.designation || ''}`,
      };
    })
    .filter((o) => o.origin !== undefined)
    .sort((a, b) => a.origin - b.origin);
}

/* Toutes les lignes d'un document, reconstituées depuis la comparaison :
 * lignes rapprochées, lignes hors BC et candidats d'ambiguïté. Chaque ligne
 * porte son contexte (avec quoi elle est rapprochée, et comment). */
export function documentLines(comparison, type) {
  const out = new Map();
  const add = (line, context) => {
    const origins = originsOf(line);
    const key = lineKey(type, origins);
    const prev = out.get(key);
    if (!prev || (prev.context.kind !== 'ambiguous' && context.kind === 'ambiguous')) {
      out.set(key, { key, type, origins, line, context });
    }
  };

  for (const p of comparison?.produits || []) {
    const l = p.lignes?.[type];
    if (!l) continue;
    if (type === 'BC') {
      add(l, { kind: 'bc', statut: p.statut, productKey: p.cle });
    } else if (isBcProduct(p)) {
      const pair = p.paires?.[PAIR_OF[type]] || {};
      add(l, {
        kind: 'matched',
        statut: pair.statut,
        productKey: p.cle,
        bcOrigin: originsOf(p.lignes.BC)[0],
        bcLine: p.lignes.BC,
      });
    } else {
      const msg = p.paires?.[PAIR_OF[type]]?.message || '';
      add(l, {
        kind: msg.includes('détachée') ? 'detached' : 'extra',
        statut: 'en_trop',
        productKey: p.cle,
      });
    }
  }

  if (type !== 'BC') {
    for (const amb of comparison?.ambiguites || []) {
      if (amb.paire !== PAIR_OF[type]) continue;
      for (const cand of amb.candidats || []) {
        if (out.has(lineKey(type, originsOf(cand)))) continue;
        add(cand, {
          kind: 'ambiguous',
          statut: 'ambigu',
          bcOrigin: originsOf(amb)[0],
          bcLabel: amb.reference,
        });
      }
    }
  }

  return [...out.values()].sort((a, b) => (a.origins[0] ?? 1e9) - (b.origins[0] ?? 1e9));
}

/* Lignes à traiter : BC non rapprochées, lignes hors BC, candidats d'ambiguïté. */
export function looseItems(comparison) {
  const items = [];
  for (const p of comparison?.produits || []) {
    if (isBcProduct(p) && !isMatchedProduct(p)) {
      const reasons = Object.keys(p.paires || {}).map((k) => (k === 'BC↔BL' ? 'Non livrée' : 'Non facturée'));
      items.push({ type: 'BC', line: p.lignes.BC, reason: reasons.join(' · '), tone: 'err' });
    }
    if (isOutsideBc(p)) {
      for (const [t, l] of Object.entries(p.lignes || {})) {
        const detached = (p.paires?.[PAIR_OF[t]]?.message || '').includes('détachée');
        items.push({
          type: t,
          line: l,
          reason: detached ? "Détachée par l'opérateur" : 'Absente du BC',
          tone: detached ? 'edit' : 'err',
        });
      }
    }
  }
  for (const amb of comparison?.ambiguites || []) {
    if (!amb.paire.startsWith('BC↔')) continue;
    const t = amb.paire.split('↔')[1];
    for (const cand of amb.candidats || []) {
      items.push({
        type: t,
        line: cand,
        reason: `Candidate pour BC ligne ${lineNo(originsOf(amb)[0])}`,
        tone: 'warn',
        suggestedBc: originsOf(amb)[0],
      });
    }
  }
  // une même ligne peut être signalée deux fois : on garde l'entrée la plus utile
  const seen = new Map();
  for (const it of items) {
    const key = lineKey(it.type, originsOf(it.line));
    const prev = seen.get(key);
    if (!prev || (prev.suggestedBc === undefined && it.suggestedBc !== undefined)) {
      seen.set(key, { ...it, key, origins: originsOf(it.line) });
    }
  }
  return [...seen.values()];
}

/* ----------------------------------------------------------- totaux */

export const TOTAL_FIELDS = [
  ['totalHT', 'Total HT', 'money'],
  ['remiseTotale', 'Remise totale', 'money'],
  ['netHT', 'Net HT', 'money'],
  ['tauxTVA', 'Taux de TVA (%)', 'rate'],
  ['montantTVA', 'Montant TVA', 'money'],
  ['timbreFiscal', 'Timbre fiscal', 'money'],
  ['totalTTC', 'Total TTC', 'money'],
  ['netAPayer', 'Net à payer', 'money'],
];

function decCount(v) {
  const s = String(v);
  const i = s.indexOf('.');
  return i < 0 ? 0 : s.length - i - 1;
}

/* Contrôle croisé d'un total entre documents. Le BC fait référence quand il
 * porte le champ ; tolérance dérivée de la précision d'affichage la plus
 * grossière, plancher relatif de 0,05 % (mêmes règles que l'ancienne interface). */
export function checkTotal(field, kind, docs) {
  const vals = docs
    .map(({ type, doc }) => ({ type, raw: doc?.totaux?.[field] }))
    .filter((x) => x.raw !== null && x.raw !== undefined && String(x.raw).trim() !== '');
  if (vals.length < 2) return { tone: 'muted', label: 'Non comparé' };
  const ref = vals.find((x) => x.type === 'BC') || vals[0];
  const refN = parseFloat(ref.raw);
  const quantum = 10 ** -Math.min(...vals.map((x) => decCount(x.raw)));
  const tol = kind === 'rate' ? quantum : Math.max(quantum, Math.abs(refN) * 0.0005);
  let worst = 0;
  for (const x of vals) {
    if (x === ref) continue;
    const delta = parseFloat(x.raw) - refN;
    if (Math.abs(delta) > tol && Math.abs(delta) > Math.abs(worst)) worst = delta;
  }
  if (worst === 0) return { tone: 'ok', label: 'Conforme' };
  const sign = worst > 0 ? '+' : '−';
  const abs = kind === 'rate' ? fmtRate(Math.abs(worst).toFixed(4)) : fmtMoney(Math.abs(worst));
  return { tone: 'err', label: `Écart ${sign}${abs}` };
}

/* Écart net facturé / commandé, sur les lignes rapprochées. */
export function invoiceGap(comparison) {
  let delta = 0;
  let notInvoiced = 0;
  let hasInvoice = false;
  for (const p of comparison?.produits || []) {
    const pair = p.paires?.['BC↔Facture'];
    if (!pair) continue;
    hasInvoice = true;
    if (pair.statut === 'manquant') notInvoiced += parseFloat(p.lignes.BC?.montantHT) || 0;
    for (const ax of pair.axes || []) {
      if (ax.champ === 'montantHT' && ax.statut === 'écart') delta += parseFloat(ax.ecart_signe) || 0;
    }
  }
  return { hasInvoice, delta, notInvoiced };
}

/* Verdict global d'une analyse (même logique que le rapport PDF). */
export function globalVerdict(analysis) {
  const c = analysis?.comparaison;
  if (analysis?.statut === 'hors périmètre') {
    return { tone: 'muted', title: 'Document hors périmètre', text: 'Le PDF ne contient pas un jeu BC + BL et/ou Facture exploitable.' };
  }
  if (!c || c.statut === 'impossible') {
    return { tone: 'err', title: 'Comparaison impossible', text: c?.message || 'Aucune comparaison disponible.' };
  }
  const t = c.totaux || {};
  if (t.ambigus) {
    return {
      tone: 'warn',
      title: 'Révision requise',
      text: `${t.ambigus} rapprochement${t.ambigus > 1 ? 's' : ''} à trancher avant de conclure.`,
    };
  }
  if (t.ecarts) {
    return {
      tone: 'err',
      title: `${t.ecarts} écart${t.ecarts > 1 ? 's' : ''} détecté${t.ecarts > 1 ? 's' : ''}`,
      text: `${t.conformes} produit${t.conformes > 1 ? 's' : ''} conforme${t.conformes > 1 ? 's' : ''} sur ${t.produits}.`,
    };
  }
  return { tone: 'ok', title: 'Documents concordants', text: `Les ${t.produits} produits concordent entre les documents.` };
}
