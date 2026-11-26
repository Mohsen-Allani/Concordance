import { Coins, Info, Receipt, TrendingDown, TrendingUp } from 'lucide-react';

import { DOC, DOC_TYPES } from '../../lib/status.js';
import { fmtDate, fmtMoney, fmtRate } from '../../lib/format.js';
import { TOTAL_FIELDS, checkTotal, docByType, invoiceGap } from '../../lib/comparison.js';

import { Card } from '../../components/ui/Card.jsx';
import { Badge, DocTag } from '../../components/ui/Badge.jsx';
import { KpiCard } from '../../components/ui/Widgets.jsx';

export default function AmountsTab({ ctx }) {
  const { analysis: a, comparison: c } = ctx;
  const docs = DOC_TYPES.map((t) => ({ type: t, doc: docByType(a, t) })).filter((x) => x.doc);
  const devise = docByType(a, 'BC')?.devise || docs.map((d) => d.doc.devise).find(Boolean) || '';
  const gap = invoiceGap(c);
  const fields = TOTAL_FIELDS.filter(([f]) => docs.some(({ doc }) => doc.totaux?.[f] !== null && doc.totaux?.[f] !== undefined));

  const bcNet = docByType(a, 'BC')?.totaux?.netHT ?? docByType(a, 'BC')?.totaux?.totalHT;
  const faNet = docByType(a, 'Facture')?.totaux?.netHT ?? docByType(a, 'Facture')?.totaux?.totalHT;

  return (
    <div className="stack">
      <div className="kpi-grid">
        <KpiCard label={`Net HT commandé ${devise ? `(${devise})` : ''}`} value={fmtMoney(bcNet)} icon={Receipt} />
        <KpiCard
          label={`Net HT facturé ${devise ? `(${devise})` : ''}`}
          value={gap.hasInvoice ? fmtMoney(faNet) : '—'}
          icon={Coins}
        />
        <KpiCard
          label="Écart net facturé / commandé"
          value={gap.delta ? `${gap.delta > 0 ? '+' : '−'}${fmtMoney(Math.abs(gap.delta))}` : gap.hasInvoice ? '0' : '—'}
          tone={gap.delta ? 'err' : 'neutral'}
          icon={gap.delta > 0 ? TrendingUp : TrendingDown}
          hint={
            gap.delta
              ? gap.delta > 0
                ? 'Surfacturation sur les lignes rapprochées'
                : 'Sous-facturation sur les lignes rapprochées'
              : 'Sur les lignes rapprochées'
          }
        />
        <KpiCard
          label="Commandé non facturé"
          value={gap.hasInvoice ? fmtMoney(gap.notInvoiced) : '—'}
          tone={gap.notInvoiced ? 'warn' : 'neutral'}
          icon={Receipt}
          hint="Montant HT des lignes du BC absentes de la facture"
        />
      </div>

      <Card
        title="Comparaison des totaux"
        subtitle="Valeurs après validation arithmétique : un total absent du document a pu être reconstruit à partir des lignes."
        padded={false}
      >
        {fields.length ? (
          <div className="table-scroll">
            <table className="table table-totals">
              <thead>
                <tr>
                  <th>Champ</th>
                  {docs.map(({ type, doc }) => (
                    <th key={type} className="text-right">
                      <div className="th-doc">
                        <span><DocTag type={type} size="sm" /> {DOC[type].short}</span>
                        <small>
                          {doc.numero || '—'} · {fmtDate(doc.date)}
                        </small>
                      </div>
                    </th>
                  ))}
                  <th className="text-center">Résultat</th>
                </tr>
              </thead>
              <tbody>
                {fields.map(([f, label, kind]) => {
                  const chk = checkTotal(f, kind, docs);
                  return (
                    <tr key={f} className={chk.tone === 'err' ? 'row-bad' : ''}>
                      <td className="cell-strong">{label}</td>
                      {docs.map(({ type, doc }) => {
                        const v = doc.totaux?.[f];
                        return (
                          <td key={type} className="text-right mono">
                            {v === null || v === undefined ? '—' : kind === 'rate' ? fmtRate(v) : fmtMoney(v)}
                          </td>
                        );
                      })}
                      <td className="text-center">
                        <Badge tone={chk.tone}>{chk.label}</Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="table-empty">Aucun total disponible sur ces documents.</div>
        )}
      </Card>

      <div className="note note-inline">
        <Info size={16} />
        Le bon de commande sert de référence. Un bon de livraison ne porte en général pas de
        montants : ses totaux apparaissent alors « Non comparé ». La tolérance suit la précision
        d'affichage des documents (le millime pour le dinar).
      </div>
    </div>
  );
}
