import { useMemo } from 'react';
import { CheckCircle2, FileWarning, GitMerge, History, ListTodo, Trash2, Unlink } from 'lucide-react';

import { DOC, DOC_TYPES, l7Verdict } from '../../lib/status.js';
import { fmtMoney, fmtQty } from '../../lib/format.js';
import { docByType, lineNo, looseItems, originsOf } from '../../lib/comparison.js';
import { describeOp, describeSaved } from '../../lib/revisions.js';

import { Card } from '../../components/ui/Card.jsx';
import Button from '../../components/ui/Button.jsx';
import { Badge, DocTag } from '../../components/ui/Badge.jsx';
import { EmptyState } from '../../components/ui/Feedback.jsx';
import { CandidateList } from './MatchingTab.jsx';
import { LineActions, LineTable } from './shared.jsx';

/* Pour une ligne BC non rapprochée : choisir une ligne BL/FA libre. */
function AttachToBc({ bcOrigin, loose, ctx }) {
  const targets = loose.filter((it) => it.type !== 'BC');
  if (!targets.length) return <span className="text-muted small">Aucune ligne libre</span>;
  return (
    <select
      className="select select-sm"
      value=""
      onChange={(e) => {
        const it = targets.find((x) => x.key === e.target.value);
        if (it) ctx.addOp({ kind: 'assign', doc: it.type, srcs: it.origins, bc: bcOrigin });
      }}
    >
      <option value="">Associer une ligne…</option>
      {targets.map((it) => (
        <option key={it.key} value={it.key}>
          {DOC[it.type].tag} l. {it.origins.map(lineNo).join('+')} — {it.line.reference || 'sans réf.'} · {(it.line.designation || '').slice(0, 50)}
        </option>
      ))}
    </select>
  );
}

export default function ReviewTab({ ctx }) {
  const { analysis: a, comparison: c, ops } = ctx;
  const ambiguities = (c.ambiguites || []).filter((x) => x.paire.startsWith('BC↔'));
  const residual = (c.ambiguites || []).filter((x) => !x.paire.startsWith('BC↔'));
  const loose = useMemo(() => looseItems(c), [c]);
  const saved = describeSaved(a.revisions);
  const docsToCheck = DOC_TYPES.map((t) => docByType(a, t)).filter((d) => d && d.verdict === 'review');

  const looseRows = loose.map((it) => ({
    key: it.key,
    type: it.type,
    origins: it.origins,
    line: it.line,
    status: (
      <Badge tone={it.tone}>{it.reason}</Badge>
    ),
    actions:
      it.type === 'BC' ? (
        <AttachToBc bcOrigin={it.origins[0]} loose={loose} ctx={ctx} />
      ) : (
        <LineActions
          type={it.type}
          origins={it.origins}
          line={it.line}
          ctx={ctx}
          canDetach={it.tone !== 'edit'}
          suggested={it.suggestedBc}
        />
      ),
  }));

  const nothingToDo = !ambiguities.length && !loose.length && !docsToCheck.length;

  return (
    <div className="stack">
      <div className="note note-inline">
        <GitMerge size={16} />
        Vos décisions ne modifient pas le résultat à la main : elles sont transmises au moteur comme
        contraintes, et toute la chaîne (validation puis rapprochement) est rejouée à l'enregistrement.
      </div>

      {nothingToDo && !ops.length && (
        <Card>
          <EmptyState icon={CheckCircle2} title="Rien à trancher" text="Aucune ambiguïté ni ligne orpheline sur cette analyse." />
        </Card>
      )}

      {ambiguities.length > 0 && (
        <Card
          title="Ambiguïtés à trancher"
          subtitle="Plusieurs lignes peuvent correspondre à une même ligne du bon de commande : le moteur refuse de choisir à votre place."
          icon={ListTodo}
        >
          <div className="stack-sm">
            {ambiguities.map((amb) => {
              const type = amb.paire.split('↔')[1];
              const bcOrigin = originsOf(amb)[0];
              const ref = amb.ligne_reference || {};
              return (
                <div key={`${amb.paire}-${amb.reference_index}`} className="amb">
                  <div className="amb-head">
                    <DocTag type="BC" size="sm" />
                    <span className="mono">l. {lineNo(bcOrigin)}</span>
                    <strong>{ref.reference || amb.reference}</strong>
                    <span className="amb-des">{ref.designation}</span>
                    <span className="amb-figures mono">
                      {fmtQty(ref.quantite)} {ref.unite || ''} · PU {fmtMoney(ref.prixUnitaireHT)}
                    </span>
                    <span className="amb-to">
                      → <DocTag type={type} size="sm" />
                    </span>
                  </div>
                  <p className="amb-motif">{amb.motif}</p>
                  <CandidateList candidates={amb.candidats || []} type={type} bcOrigin={bcOrigin} ctx={ctx} />
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {residual.length > 0 && (
        <Card title="Ambiguïtés hors commande" subtitle="Entre lignes absentes du BC (BL ↔ Facture) : informatives, non révisables." >
          <ul className="bullet-list">
            {residual.map((amb, i) => (
              <li key={i}>
                {amb.paire} — « {amb.reference} » : {amb.motif} ({(amb.candidats || []).length} candidats)
              </li>
            ))}
          </ul>
        </Card>
      )}

      {loose.length > 0 && (
        <Card
          title="Lignes non rapprochées"
          subtitle="Affectez une ligne livrée ou facturée à la bonne ligne du bon de commande, ou détachez-la si elle n'y correspond pas."
          icon={Unlink}
          padded={false}
        >
          <LineTable rows={looseRows} ctx={ctx} showStatus />
        </Card>
      )}

      {docsToCheck.length > 0 && (
        <Card title="Documents à vérifier" subtitle="Contrôle arithmétique non certifié : une valeur a peut-être été mal lue." icon={FileWarning}>
          <ul className="doc-checks">
            {docsToCheck.map((d) => (
              <li key={d.type}>
                <DocTag type={d.type} size="sm" />
                <strong>{DOC[d.type].label}</strong>
                <span className="mono">{d.numero || '—'}</span>
                <Badge tone={l7Verdict(d.verdict).tone}>{l7Verdict(d.verdict).label}</Badge>
                <button className="link" onClick={() => ctx.goTab('documents', { doc: d.type })}>
                  Contrôler les lignes
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="grid-2">
        <Card title="Modifications en attente" subtitle={ops.length ? 'Appliquées à l’enregistrement' : undefined} icon={ListTodo} padded={false}>
          {ops.length ? (
            <ul className="journal">
              {ops.map((op) => (
                <li key={op.id}>
                  <Badge tone="edit" dot={false}>
                    {op.kind === 'assign' ? 'Affectation' : op.kind === 'detach' ? 'Détachement' : 'Correction'}
                  </Badge>
                  <span>{describeOp(op)}</span>
                  <Button size="xs" variant="ghost" icon={Trash2} title="Retirer" onClick={() => ctx.removeOp(op.id)} />
                </li>
              ))}
            </ul>
          ) : (
            <div className="table-empty">Aucune modification en attente.</div>
          )}
        </Card>

        <Card title="Révisions enregistrées" subtitle="Piste d'audit de cette analyse" icon={History} padded={false}>
          {saved.length ? (
            <ul className="journal">
              {saved.map((s, i) => (
                <li key={i}>
                  <Badge tone="muted" dot={false}>
                    {s.kind === 'assign' ? 'Affectation' : s.kind === 'detach' ? 'Détachement' : 'Correction'}
                  </Badge>
                  <span>{s.text}</span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="table-empty">Aucune révision enregistrée.</div>
          )}
        </Card>
      </div>
    </div>
  );
}
