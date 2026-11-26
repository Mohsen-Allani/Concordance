import { Fragment, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Check, ChevronDown, ChevronRight } from 'lucide-react';

import { DOC, DOC_TYPES, PAIR_OF, productStatus } from '../../lib/status.js';
import { fmtMoney, fmtQty } from '../../lib/format.js';
import {
  gapFields,
  isBcProduct,
  lineKey,
  lineNo,
  originsOf,
  presentTargets,
  productSummary,
  statusCounts,
} from '../../lib/comparison.js';

import { Card } from '../../components/ui/Card.jsx';
import Button from '../../components/ui/Button.jsx';
import { Badge, DocTag, ProductStatusBadge } from '../../components/ui/Badge.jsx';
import { FilterChips, SearchInput } from '../../components/ui/Widgets.jsx';
import { EmptyState } from '../../components/ui/Feedback.jsx';
import { AxesTable, LineActions, LineTable } from './shared.jsx';

const FILTERS = {
  all: () => true,
  ecarts: (p) => ['écart', 'manquant', 'en_trop'].includes(p.statut),
  ambigu: (p) => p.statut === 'ambigu',
  conforme: (p) => p.statut === 'conforme',
  non_comparable: (p) => p.statut === 'non_comparable',
};

/* Candidats d'une ambiguïté BC↔cible, avec bouton « Choisir ». */
export function CandidateList({ candidates, type, bcOrigin, ctx }) {
  const chosen = (cand) =>
    ctx.ops.some(
      (op) => op.kind === 'assign' && op.doc === type && op.bc === bcOrigin &&
        op.srcs.join(',') === originsOf(cand).join(','),
    );
  return (
    <table className="table table-compact">
      <thead>
        <tr>
          <th className="col-no">L.</th>
          <th>Référence</th>
          <th>Désignation</th>
          <th className="text-right">Qté</th>
          <th className="text-right">PU HT</th>
          <th className="text-right">Montant HT</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {candidates.map((cand) => (
          <tr key={originsOf(cand).join(',')}>
            <td className="mono text-muted">{originsOf(cand).map(lineNo).join('+')}</td>
            <td className="mono">{cand.reference || '—'}</td>
            <td>{cand.designation || '—'}</td>
            <td className="text-right mono">{fmtQty(cand.quantite)}</td>
            <td className="text-right mono">{fmtMoney(cand.prixUnitaireHT)}</td>
            <td className="text-right mono">{fmtMoney(cand.montantHT)}</td>
            <td className="text-right">
              {chosen(cand) ? (
                <Badge tone="edit" dot={false}>
                  <Check size={12} /> Choisi
                </Badge>
              ) : (
                <Button
                  size="xs"
                  variant="primary"
                  onClick={() => ctx.addOp({ kind: 'assign', doc: type, srcs: originsOf(cand), bc: bcOrigin })}
                >
                  Choisir
                </Button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ProductDetail({ p, ctx }) {
  const bad = gapFields(p);
  const bcOrigin = originsOf(p.lignes.BC)[0];
  const rows = [];

  for (const t of DOC_TYPES) {
    const l = p.lignes?.[t];
    if (l) {
      const origins = originsOf(l);
      const pair = p.paires?.[PAIR_OF[t]];
      rows.push({
        key: lineKey(t, origins),
        type: t,
        origins,
        line: l,
        badFields: bad[t],
        actions: (
          <LineActions
            type={t}
            origins={origins}
            line={l}
            ctx={ctx}
            canDetach={t !== 'BC' && !(pair?.message || '').includes('détachée')}
            currentBc={isBcProduct(p) && t !== 'BC' ? bcOrigin : undefined}
          />
        ),
      });
      continue;
    }
    if (t === 'BC') continue;
    const pair = p.paires?.[PAIR_OF[t]];
    if (pair?.statut === 'manquant') {
      rows.push({
        key: `${t}-ghost`,
        type: t,
        ghost: { tone: 'err', title: t === 'BL' ? 'Non livré' : 'Non facturé', text: '— aucune ligne rapprochée' },
      });
    } else if (pair?.statut === 'ambigu') {
      rows.push({
        key: `${t}-ghost`,
        type: t,
        ghost: { tone: 'warn', title: 'Ambigu', text: `— ${(pair.candidats || []).length} candidats, voir ci-dessous` },
      });
    }
  }

  const pairs = Object.entries(p.paires || {});
  return (
    <div className="product-detail">
      <LineTable rows={rows} ctx={ctx} />
      <div className="pair-grid">
        {pairs.map(([key, pair]) => {
          const [left, right] = key.split('↔');
          const s = productStatus(pair.statut);
          return (
            <div key={key} className="pair-card">
              <div className="pair-card-head">
                <span className="nowrap">
                  <DocTag type={left} size="sm" />
                  <span className="pair-arrow">↔</span>
                  <DocTag type={right} size="sm" />
                </span>
                <Badge tone={s.tone}>{s.label}</Badge>
                {pair.score_appariement !== undefined && (
                  <span className="text-muted small">
                    score d'appariement <b className="mono">{pair.score_appariement}</b>
                  </span>
                )}
              </div>
              {pair.axes && <AxesTable axes={pair.axes} left={DOC[left]?.tag} right={DOC[right]?.tag} />}
              {pair.message && <p className="pair-message">{pair.message}</p>}
              {pair.deduit && <p className="pair-message">Déduit : {pair.deduit}.</p>}
              {pair.statut === 'ambigu' && (
                <>
                  <p className="pair-message">{pair.motif} — choisissez la bonne ligne :</p>
                  <CandidateList candidates={pair.candidats || []} type={right} bcOrigin={bcOrigin} ctx={ctx} />
                </>
              )}
              {(pair.preuves || []).length > 0 && (
                <ul className="proofs">
                  {pair.preuves.map((pr) => (
                    <li key={pr}>{pr}</li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function MatchingTab({ ctx }) {
  const c = ctx.comparison;
  const [params, setParams] = useSearchParams();
  const filter = params.get('filtre') || 'all';
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(() => new Set());
  const targets = presentTargets(c);

  const counts = statusCounts(c.produits);
  const options = [
    { key: 'all', label: 'Tous', count: c.produits.length },
    { key: 'ecarts', label: 'Écarts', tone: 'err', count: counts['écart'] + counts.manquant + counts.en_trop },
    { key: 'ambigu', label: 'À trancher', tone: 'warn', count: counts.ambigu },
    { key: 'conforme', label: 'Conformes', tone: 'ok', count: counts.conforme },
    { key: 'non_comparable', label: 'Non comparables', count: counts.non_comparable },
  ];

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return c.produits.filter((p) => {
      if (!(FILTERS[filter] || FILTERS.all)(p)) return false;
      if (!q) return true;
      return `${p.reference || ''} ${p.designation || ''}`.toLowerCase().includes(q);
    });
  }, [c.produits, filter, query]);

  const toggle = (key) =>
    setOpen((s) => {
      const n = new Set(s);
      if (n.has(key)) n.delete(key);
      else n.add(key);
      return n;
    });

  const qty = (p, t) => (p.lignes?.[t] ? fmtQty(p.lignes[t].quantite) : '·');
  const bad = (p, t, f) => (p.paires?.[PAIR_OF[t]]?.axes || []).some((ax) => ax.champ === f && ax.statut === 'écart');

  return (
    <Card padded={false}>
      <div className="toolbar">
        <FilterChips
          value={filter}
          onChange={(k) => setParams(k === 'all' ? { onglet: 'rapprochement' } : { onglet: 'rapprochement', filtre: k }, { replace: true })}
          options={options}
        />
        <div className="toolbar-right">
          <button
            className="link small"
            onClick={() => setOpen(open.size ? new Set() : new Set(rows.map((p) => p.cle)))}
          >
            {open.size ? 'Tout replier' : 'Tout déplier'}
          </button>
          <SearchInput value={query} onChange={setQuery} placeholder="Référence ou désignation" />
        </div>
      </div>

      {!rows.length ? (
        <EmptyState title="Aucun produit" text="Aucun produit ne correspond à ce filtre." />
      ) : (
        <div className="table-scroll">
          <table className="table table-products">
            <thead>
              <tr>
                <th className="col-toggle" />
                <th>Statut</th>
                <th>Référence</th>
                <th>Désignation</th>
                <th className="text-right">Qté BC</th>
                {targets.map((t) => (
                  <th key={t} className="text-right">Qté {DOC[t].tag}</th>
                ))}
                <th className="text-right">PU BC</th>
                {targets.includes('Facture') && <th className="text-right">PU FA</th>}
                <th>Constat</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => {
                const isOpen = open.has(p.cle);
                const sum = productSummary(p);
                return (
                  <Fragment key={p.cle}>
                    <tr className={`row-product ${isOpen ? 'row-open' : ''} row-tone-${productStatus(p.statut).tone}`} onClick={() => toggle(p.cle)}>
                      <td>{isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</td>
                      <td><ProductStatusBadge statut={p.statut} /></td>
                      <td className="mono">{p.reference || '—'}</td>
                      <td className="cell-designation">{p.designation || '—'}</td>
                      <td className="text-right mono">{qty(p, 'BC')}</td>
                      {targets.map((t) => (
                        <td key={t} className={`text-right mono ${bad(p, t, 'quantite') ? 'cell-bad' : ''}`}>{qty(p, t)}</td>
                      ))}
                      <td className="text-right mono">{p.lignes?.BC ? fmtMoney(p.lignes.BC.prixUnitaireHT) : '·'}</td>
                      {targets.includes('Facture') && (
                        <td className={`text-right mono ${bad(p, 'Facture', 'prixUnitaireHT') ? 'cell-bad' : ''}`}>
                          {p.lignes?.Facture ? fmtMoney(p.lignes.Facture.prixUnitaireHT) : '·'}
                        </td>
                      )}
                      <td className="cell-summary">
                        <strong>{sum.title}</strong>
                        <span>{sum.details.join(' · ')}</span>
                      </td>
                    </tr>
                    {isOpen && (
                      <tr className="row-detail">
                        <td colSpan={7 + targets.length + (targets.includes('Facture') ? 1 : 0)}>
                          <ProductDetail p={p} ctx={ctx} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
