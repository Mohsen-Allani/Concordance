import {
  AlertTriangle,
  ArrowRight,
  Building2,
  CheckCircle2,
  CircleSlash,
  ListChecks,
  ShieldCheck,
  XCircle,
} from 'lucide-react';

import { CHECK_STATUS, DOC, DOC_TYPES, l7Verdict, productStatus } from '../../lib/status.js';
import { fmtDate } from '../../lib/format.js';
import { docByType, globalVerdict, productSummary, statusCounts } from '../../lib/comparison.js';

import { Card } from '../../components/ui/Card.jsx';
import Button from '../../components/ui/Button.jsx';
import { Badge, DocTag } from '../../components/ui/Badge.jsx';
import { ConfidenceMeter, KpiCard, StackBar } from '../../components/ui/Widgets.jsx';

const VERDICT_ICON = { ok: CheckCircle2, err: XCircle, warn: AlertTriangle, muted: CircleSlash };
const GAP_STATUSES = ['écart', 'manquant', 'en_trop'];

function Party({ role, party }) {
  return (
    <div className="party">
      <div className="eyebrow">{role}</div>
      <div className="party-name">{party?.nom || '—'}</div>
      <div className="party-details">
        {party?.matriculeFiscal && (
          <span>
            MF <span className="mono">{party.matriculeFiscal}</span>
          </span>
        )}
        {party?.code && (
          <span>
            Code <span className="mono">{party.code}</span>
          </span>
        )}
        {party?.adresse && <span>{party.adresse}</span>}
      </div>
    </div>
  );
}

export default function SummaryTab({ ctx }) {
  const { analysis: a, comparison: c } = ctx;
  const verdict = globalVerdict(a);
  const VIcon = VERDICT_ICON[verdict.tone] || AlertTriangle;
  const docs = DOC_TYPES.map((t) => docByType(a, t)).filter(Boolean);
  const comparable = c && c.statut !== 'impossible';

  const counts = statusCounts(c?.produits);
  const gaps = (c?.produits || []).filter((p) => GAP_STATUSES.includes(p.statut));
  const ref = docByType(a, 'BC') || docs[0] || {};
  const headerChecks = c?.entete || [];
  const warnings = headerChecks.filter((x) => x.statut === 'warning').length;

  return (
    <div className="stack">
      <div className={`verdict verdict-${verdict.tone}`}>
        <VIcon size={26} />
        <div>
          <h2>{verdict.title}</h2>
          <p>{verdict.text}</p>
        </div>
        {comparable && (c.ambiguites || []).length > 0 && (
          <Button variant="primary" icon={ArrowRight} onClick={() => ctx.goTab('revision')}>
            Trancher les ambiguïtés
          </Button>
        )}
      </div>

      {!comparable && (
        <Card title="Pourquoi la comparaison n'a pas eu lieu" icon={AlertTriangle}>
          <ul className="bullet-list">
            {[...(a.erreurs || []), ...(c?.message ? [c.message] : [])].map((m) => (
              <li key={m}>{m}</li>
            ))}
            {!(a.erreurs || []).length && !c?.message && (
              <li>Le PDF doit contenir un bon de commande et au moins un bon de livraison ou une facture.</li>
            )}
          </ul>
        </Card>
      )}

      {comparable && (
        <>
          <div className="kpi-grid">
            <KpiCard label="Produits contrôlés" value={c.totaux.produits} icon={ListChecks} />
            <KpiCard label="Conformes" value={c.totaux.conformes} tone="ok" icon={CheckCircle2} />
            <KpiCard
              label="Écarts"
              value={c.totaux.ecarts}
              tone={c.totaux.ecarts ? 'err' : 'neutral'}
              icon={XCircle}
              hint="Quantité, prix, manquants, en trop"
              onClick={c.totaux.ecarts ? () => ctx.goTab('rapprochement', { filtre: 'ecarts' }) : undefined}
            />
            <KpiCard
              label="À trancher"
              value={c.totaux.ambigus}
              tone={c.totaux.ambigus ? 'warn' : 'neutral'}
              icon={AlertTriangle}
              hint="Rapprochements ambigus"
              onClick={c.totaux.ambigus ? () => ctx.goTab('revision') : undefined}
            />
          </div>

          <Card title="Répartition des produits">
            <StackBar
              height={12}
              segments={Object.entries(counts).map(([k, v]) => ({
                key: k,
                value: v,
                label: productStatus(k).label,
                tone: productStatus(k).tone === 'err' ? (k === 'écart' ? 'err' : k === 'manquant' ? 'err2' : 'err3') : productStatus(k).tone,
              }))}
            />
            <div className="legend legend-wrap">
              {Object.entries(counts)
                .filter(([, v]) => v > 0)
                .map(([k, v]) => (
                  <span key={k}>
                    <Badge tone={productStatus(k).tone}>{productStatus(k).label}</Badge>
                    <b className="mono">{v}</b>
                  </span>
                ))}
            </div>
          </Card>
        </>
      )}

      <div className="grid-2-1">
        <Card title="Parties" icon={Building2}>
          <div className="parties">
            <Party role="Fournisseur" party={ref.fournisseur} />
            <ArrowRight size={18} className="parties-arrow" />
            <Party role="Client" party={ref.client} />
          </div>
          <div className="parties-foot">
            Devise <b>{ref.devise || docs.map((d) => d.devise).find(Boolean) || '—'}</b> · montants hors taxes
          </div>
        </Card>

        <Card
          title="Contrôles d'en-tête"
          icon={ShieldCheck}
          subtitle={headerChecks.length ? (warnings ? `${warnings} point(s) à vérifier` : 'Aucune incohérence') : undefined}
          padded={false}
        >
          {headerChecks.length ? (
            <ul className="checks">
              {headerChecks.map((chk, i) => {
                const s = CHECK_STATUS[chk.statut] || { label: chk.statut, tone: 'muted' };
                return (
                  <li key={i} className={`check check-${s.tone}`}>
                    <Badge tone={s.tone}>{s.label}</Badge>
                    <div>
                      <strong>{chk.nom}</strong>
                      <span>{chk.message}</span>
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : (
            <div className="table-empty">Aucun contrôle disponible.</div>
          )}
        </Card>
      </div>

      <div className="doc-cards">
        {docs.map((d) => {
          const v = l7Verdict(d.verdict);
          const nb = c?.documents?.[d.type]?.lignes ?? d.nb_lignes;
          return (
            <button key={d.type} className="doc-card" onClick={() => ctx.goTab('documents', { doc: d.type })}>
              <div className="doc-card-head">
                <DocTag type={d.type} />
                <span className="doc-card-label">{DOC[d.type].label}</span>
                <Badge tone={v.tone} title={v.hint}>{v.label}</Badge>
              </div>
              <div className="doc-card-num mono">{d.numero || 'sans numéro'}</div>
              <div className="doc-card-meta">
                <span>{fmtDate(d.date)}</span>
                <span>{nb ?? '?'} ligne{nb > 1 ? 's' : ''}</span>
                <span>{d.est_scanne ? 'Scanné' : 'Natif'}</span>
              </div>
              <div className="doc-card-conf">
                <span className="text-muted small">Confiance d'extraction</span>
                <ConfidenceMeter value={d.confiance} />
              </div>
            </button>
          );
        })}
      </div>

      {comparable && (
        <div className="grid-2-1">
          <Card
            title="Principaux écarts"
            subtitle={gaps.length ? `${gaps.length} produit(s) concerné(s)` : undefined}
            padded={false}
            actions={
              gaps.length > 0 && (
                <button className="link" onClick={() => ctx.goTab('rapprochement', { filtre: 'ecarts' })}>
                  Tout voir <ArrowRight size={14} />
                </button>
              )
            }
          >
            {gaps.length ? (
              <ul className="issues">
                {gaps.slice(0, 6).map((p) => {
                  const sum = productSummary(p);
                  return (
                    <li key={p.cle}>
                      <Badge tone="err">{sum.title}</Badge>
                      <div>
                        <strong>
                          <span className="mono">{p.reference || '—'}</span> · {p.designation || '—'}
                        </strong>
                        <span>{sum.details.join(' · ')}</span>
                      </div>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <div className="table-empty">Aucun écart détecté.</div>
            )}
          </Card>

          <Card title="Synthèse par paire de documents" padded={false}>
            <table className="table table-compact">
              <thead>
                <tr>
                  <th>Paire</th>
                  <th className="text-right">Conf.</th>
                  <th className="text-right">Écarts</th>
                  <th className="text-right">Manq.</th>
                  <th className="text-right">En trop</th>
                  <th className="text-right">Ambigus</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(c.synthese || {}).map(([pair, s]) => (
                  <tr key={pair}>
                    <td className="nowrap">
                      {pair.split('↔').map((t, i) => (
                        <span key={t}>
                          {i > 0 && <span className="pair-arrow">↔</span>}
                          <DocTag type={t} size="sm" />
                        </span>
                      ))}
                    </td>
                    <td className="text-right mono text-ok">{s.conforme}</td>
                    <td className="text-right mono">{s['écart'] || '·'}</td>
                    <td className="text-right mono">{s.manquant || '·'}</td>
                    <td className="text-right mono">{s.en_trop || '·'}</td>
                    <td className="text-right mono">{s.ambigu || '·'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>
      )}
    </div>
  );
}
