/* Traduction des clés internes du backend en libellés et tonalités
 * d'affichage. Les clés restent la seule vérité ; ici on ne fait que
 * les présenter. Tonalités : ok | err | warn | info | muted | edit. */

export const DOC_TYPES = ['BC', 'BL', 'Facture'];
export const TARGET_TYPES = ['BL', 'Facture'];

export const DOC = {
  BC: { tag: 'BC', label: 'Bon de commande', short: 'Commande' },
  BL: { tag: 'BL', label: 'Bon de livraison', short: 'Livraison' },
  Facture: { tag: 'FA', label: 'Facture', short: 'Facture' },
};

export const PAIR_OF = { BL: 'BC↔BL', Facture: 'BC↔Facture' };

/* Statut global d'une analyse (ligne d'historique ou détail). */
export function analysisStatus(a) {
  const ecarts = a?.totaux?.ecarts || 0;
  switch (a?.statut) {
    case 'en attente de révision':
      return { key: 'review', label: 'À réviser', tone: 'warn' };
    case 'hors périmètre':
      return { key: 'scope', label: 'Hors périmètre', tone: 'muted' };
    case 'erreur':
      return { key: 'error', label: 'Erreur', tone: 'err' };
    case 'en cours':
      return { key: 'running', label: 'En cours', tone: 'info' };
    default:
      if (ecarts > 0) {
        return { key: 'gaps', label: `${ecarts} écart${ecarts > 1 ? 's' : ''}`, tone: 'err' };
      }
      return { key: 'ok', label: 'Conforme', tone: 'ok' };
  }
}

/* Statut d'un produit ou d'une paire (L8). */
export const PRODUCT_STATUS = {
  conforme: { label: 'Conforme', tone: 'ok' },
  écart: { label: 'Écart', tone: 'err' },
  manquant: { label: 'Manquant', tone: 'err' },
  en_trop: { label: 'En trop', tone: 'err' },
  ambigu: { label: 'À trancher', tone: 'warn' },
  non_comparable: { label: 'Non comparable', tone: 'muted' },
};

export function productStatus(key) {
  return PRODUCT_STATUS[key] || { label: key || '—', tone: 'muted' };
}

/* Verdict de validation arithmétique d'un document (L7). */
export const L7_VERDICT = {
  ok: { label: 'Validé', tone: 'ok', hint: 'Chaîne arithmétique vérifiée' },
  corrected: { label: 'Corrigé', tone: 'info', hint: 'Valeurs reconstruites par le solveur' },
  review: { label: 'À vérifier', tone: 'warn', hint: 'Incohérences arithmétiques à contrôler' },
};

export function l7Verdict(key) {
  return L7_VERDICT[key] || { label: key || '—', tone: 'muted', hint: '' };
}

/* Contrôles d'en-tête (identité des parties, références croisées, dates). */
export const CHECK_STATUS = {
  ok: { label: 'Conforme', tone: 'ok' },
  warning: { label: 'À vérifier', tone: 'warn' },
  'ignoré': { label: 'Non contrôlé', tone: 'muted' },
};

export const FIELD_LABEL = {
  reference: 'Référence',
  designation: 'Désignation',
  unite: 'Unité',
  quantite: 'Quantité',
  prixUnitaireHT: 'Prix unitaire HT',
  tauxRemise: 'Remise (%)',
  montantHT: 'Montant HT',
};

export const NATURE_LABEL = {
  SOUS_LIVRAISON: 'Sous-livraison',
  SUR_LIVRAISON: 'Sur-livraison',
};
