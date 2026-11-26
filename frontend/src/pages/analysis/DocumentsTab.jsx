import { useSearchParams } from 'react-router-dom';
import { Building2, FileText, Info } from 'lucide-react';

import { DOC, DOC_TYPES, l7Verdict, productStatus } from '../../lib/status.js';
import { fmtDate, fmtMoney, fmtRate } from '../../lib/format.js';
import { TOTAL_FIELDS, docByType, documentLines, gapFields, lineNo } from '../../lib/comparison.js';

import { Card } from '../../components/ui/Card.jsx';
import Tabs from '../../components/ui/Tabs.jsx';
import { Badge, DocTag } from '../../components/ui/Badge.jsx';
import { ConfidenceMeter, KeyValue } from '../../components/ui/Widgets.jsx';
import { LineActions, LineTable } from './shared.jsx';

function situation(entry) {
  const { context: cx } = entry;
  if (cx.kind === 'bc') {
    const s = productStatus(cx.statut);
    return <Badge tone={s.tone}>{s.label}</Badge>;
  }
  if (cx.kind === 'matched') {
    const s = productStatus(cx.statut);
    return (
      <span className="situation">
        <Badge tone={s.tone}>{s.label}</Badge>
        <small>BC l. {lineNo(cx.bcOrigin)}</small>
      </span>
    );
  }
  if (cx.kind === 'ambiguous') {
    return (
      <span className="situation">
        <Badge tone="warn">À trancher</Badge>
        <small>candidate BC l. {lineNo(cx.bcOrigin)}</small>
      </span>
    );
  }
  if (cx.kind === 'detached') return <Badge tone="edit">Détachée</Badge>;
  return <Badge tone="err">Hors commande</Badge>;
}

function PartyBlock({ title, party }) {
  return (
    <div className="party-block">
      <div className="eyebrow">{title}</div>
      <dl className="kv-list">
        <KeyValue label="Raison sociale">{party?.nom}</KeyValue>
        <KeyValue label="Matricule fiscal" mono>{party?.matriculeFiscal}</KeyValue>
        <KeyValue label="Code" mono>{party?.code}</KeyValue>
        <KeyValue label="Adresse">{party?.adresse}</KeyValue>
      </dl>
    </div>
  );
}

export default function DocumentsTab({ ctx }) {
  const { analysis: a, comparison: c } = ctx;
  const [params, setParams] = useSearchParams();
  const present = DOC_TYPES.filter((t) => docByType(a, t));
  const type = present.includes(params.get('doc')) ? params.get('doc') : present[0];

  if (!type) {
    return <Card><div className="table-empty">Aucun document extrait pour cette analyse.</div></Card>;
  }

  const doc = docByType(a, type);
  const v = l7Verdict(doc.verdict);
  const comparable = c && c.statut !== 'impossible';
  const entries = comparable ? documentLines(c, type) : [];

  // Champs en écart, rapportés aux lignes de ce document.
  const badByLine = new Map();
  for (const p of comparable ? c.produits : []) {
    const l = p.lignes?.[type];
    if (l) badByLine.set((l.lignes_source || []).join(','), gapFields(p)[type]);
  }

  const rows = entries.map((e) => ({
    key: e.key,
    type,
    origins: e.origins,
    line: e.line,
    badFields: badByLine.get(e.origins.join(',')),
    status: situation(e),
    actions: (
      <LineActions
        type={type}
        origins={e.origins}
        line={e.line}
        ctx={ctx}
        canDetach={e.context.kind !== 'detached'}
        suggested={e.context.kind === 'ambiguous' ? e.context.bcOrigin : undefined}
        currentBc={e.context.kind === 'matched' ? e.context.bcOrigin : undefined}
      />
    ),
  }));

  const totals = TOTAL_FIELDS.filter(([f]) => doc.totaux?.[f] !== null && doc.totaux?.[f] !== undefined);

  return (
    <div className="stack">
      <Tabs
        variant="pill"
        value={type}
        onChange={(t) => setParams({ onglet: 'documents', doc: t }, { replace: true })}
        tabs={present.map((t) => ({ key: t, label: DOC[t].label }))}
      />

      <div className="grid-2-1">
        <Card
          title={
            <span className="doc-title">
              <DocTag type={type} /> {DOC[type].label} <span className="mono">{doc.numero || 'sans numéro'}</span>
            </span>
          }
          icon={FileText}
        >
          <dl className="kv-grid">
            <KeyValue label="Date">{fmtDate(doc.date)}</KeyValue>
            <KeyValue label="Devise">{doc.devise}</KeyValue>
            <KeyValue label="Nature">{doc.est_scanne ? 'Document scanné (prétraité)' : 'PDF natif'}</KeyValue>
            <KeyValue label="Lignes extraites">{doc.nb_lignes}</KeyValue>
            <KeyValue label="Validation arithmétique">
              <Badge tone={v.tone} title={v.hint}>{v.label}</Badge>
            </KeyValue>
            <KeyValue label="Confiance">
              <ConfidenceMeter value={doc.confiance} />
            </KeyValue>
          </dl>
          {doc.verdict === 'review' && (
            <div className="alert alert-warn">
              <Info size={16} />
              <div>
                Les montants de ce document ne se recoupent pas entièrement. Vérifiez les lignes
                ci-dessous et corrigez une valeur mal lue avec le bouton crayon.
              </div>
            </div>
          )}
        </Card>

        <Card title="Totaux du document" padded={false}>
          {totals.length ? (
            <table className="table table-compact">
              <tbody>
                {totals.map(([f, label, kind]) => (
                  <tr key={f}>
                    <td>{label}</td>
                    <td className="text-right mono cell-strong">
                      {kind === 'rate' ? fmtRate(doc.totaux[f]) : fmtMoney(doc.totaux[f])}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="table-empty">Aucun total sur ce document.</div>
          )}
        </Card>
      </div>

      <Card title="Parties" icon={Building2}>
        <div className="grid-2">
          <PartyBlock title="Fournisseur" party={doc.fournisseur} />
          <PartyBlock title="Client" party={doc.client} />
        </div>
      </Card>

      <Card
        title="Lignes du document"
        subtitle={comparable ? `${rows.length} ligne(s) — avec leur situation dans le rapprochement` : undefined}
        padded={false}
      >
        {comparable ? (
          <LineTable rows={rows} ctx={ctx} showType={false} showStatus />
        ) : (
          <div className="table-empty">
            Le détail des lignes n'est disponible que pour une analyse comparée.
          </div>
        )}
      </Card>
    </div>
  );
}
