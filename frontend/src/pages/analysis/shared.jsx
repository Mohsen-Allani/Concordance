import { useEffect, useMemo, useState } from 'react';
import { Link2Off, PencilLine } from 'lucide-react';

import { DOC, FIELD_LABEL, NATURE_LABEL, productStatus } from '../../lib/status.js';
import { fmtMoney, fmtQty, fmtRate, fmtSigned } from '../../lib/format.js';
import { bcLineOptions, lineNo } from '../../lib/comparison.js';
import { EDITABLE_FIELDS, validateField } from '../../lib/revisions.js';

import { Badge, DocTag } from '../../components/ui/Badge.jsx';
import Button from '../../components/ui/Button.jsx';
import Modal from '../../components/ui/Modal.jsx';

/* ------------------------------------------------ marqueurs de ligne */

export function LineMarkers({ type, origins, ctx }) {
  const saved = origins
    .map((o) => ctx.savedCorrections?.[type]?.[String(o)])
    .filter(Boolean);
  const pending = origins.some((o) => ctx.touched.has(`${type}:${o}`));
  return (
    <>
      {origins.length > 1 && (
        <Badge tone="info" dot={false} title={`Lignes d'origine ${origins.map((o) => o + 1).join(', ')} fusionnées (même référence)`}>
          Fusion
        </Badge>
      )}
      {saved.length > 0 && (
        <Badge
          tone="edit"
          dot={false}
          title={saved.map((f) => Object.entries(f).map(([k, v]) => `${FIELD_LABEL[k] || k} = ${v ?? '(vide)'}`).join(', ')).join(' ; ')}
        >
          Corrigée
        </Badge>
      )}
      {pending && (
        <Badge tone="edit" title="Modification en attente d'enregistrement">
          Modifiée
        </Badge>
      )}
    </>
  );
}

/* ---------------------------------------------- actions de révision */

/* Liste « affecter à une ligne du BC » (lignes BL / Facture). */
export function AssignSelect({ type, origins, ctx, suggested, currentBc }) {
  const options = useMemo(() => bcLineOptions(ctx.comparison), [ctx.comparison]);
  if (!origins.length || type === 'BC') return null;
  return (
    <select
      className="select select-sm"
      value=""
      onChange={(e) => {
        if (e.target.value === '') return;
        ctx.addOp({ kind: 'assign', doc: type, srcs: origins, bc: Number(e.target.value) });
      }}
      title="Rapprocher cette ligne d'une ligne du bon de commande"
    >
      <option value="">{currentBc !== undefined ? 'Réaffecter à…' : 'Affecter à…'}</option>
      {options.map((o) => (
        <option key={o.origin} value={o.origin} disabled={o.origin === currentBc}>
          {o.origin === suggested ? '★ ' : ''}
          {o.label.length > 70 ? `${o.label.slice(0, 70)}…` : o.label}
        </option>
      ))}
    </select>
  );
}

export function LineActions({ type, origins, line, ctx, canDetach, suggested, currentBc }) {
  const editable = origins.length === 1;
  return (
    <div className="line-actions">
      {editable && (
        <Button
          size="xs"
          variant="ghost"
          icon={PencilLine}
          title="Corriger une valeur lue"
          onClick={() => ctx.openCorrection({ type, origin: origins[0], line })}
        />
      )}
      {type !== 'BC' && (
        <AssignSelect type={type} origins={origins} ctx={ctx} suggested={suggested} currentBc={currentBc} />
      )}
      {type !== 'BC' && canDetach && origins.length > 0 && (
        <Button
          size="xs"
          variant="ghost"
          icon={Link2Off}
          title="Détacher : laisser cette ligne non rapprochée"
          onClick={() => ctx.addOp({ kind: 'detach', doc: type, srcs: origins })}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------- tableau de lignes */

const NUM_COLS = [
  ['quantite', 'Qté', fmtQty],
  ['unite', 'Unité', (v) => v || '—'],
  ['prixUnitaireHT', 'PU HT', fmtMoney],
  ['tauxRemise', 'Remise %', fmtRate],
  ['montantHT', 'Montant HT', fmtMoney],
];

/* rows : [{ key, type, origins, line, status?, badFields?: Set, actions?, ghost? }] */
export function LineTable({ rows, ctx, showType = true, showStatus = false, showActions = true, empty }) {
  if (!rows.length) return <div className="table-empty">{empty || 'Aucune ligne.'}</div>;
  return (
    <div className="table-scroll">
      <table className="table table-lines">
        <thead>
          <tr>
            {showType && <th className="col-doc">Doc</th>}
            <th className="col-no">L.</th>
            <th>Référence</th>
            <th>Désignation</th>
            {NUM_COLS.map(([f, label]) => (
              <th key={f} className={f === 'unite' ? '' : 'text-right'}>{label}</th>
            ))}
            {showStatus && <th>Situation</th>}
            {showActions && <th className="col-actions" />}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) =>
            r.ghost ? (
              <tr key={r.key} className={`row-ghost row-ghost-${r.ghost.tone}`}>
                {showType && <td><DocTag type={r.type} size="sm" /></td>}
                <td colSpan={7 + (showStatus ? 1 : 0)} className="ghost-cell">
                  <strong>{r.ghost.title}</strong> {r.ghost.text}
                </td>
                {showActions && <td>{r.ghost.action}</td>}
              </tr>
            ) : (
              <tr key={r.key} className={ctx.touched && r.origins.some((o) => ctx.touched.has(`${r.type}:${o}`)) ? 'row-pending' : ''}>
                {showType && <td><DocTag type={r.type} size="sm" /></td>}
                <td className="mono text-muted">{r.origins.map(lineNo).join('+') || '—'}</td>
                <td className={`mono ${r.badFields?.has('reference') ? 'cell-bad' : ''}`}>{r.line.reference || '—'}</td>
                <td className="cell-designation">
                  <span>{r.line.designation || '—'}</span>
                  <LineMarkers type={r.type} origins={r.origins} ctx={ctx} />
                </td>
                {NUM_COLS.map(([f, , fmt]) => (
                  <td key={f} className={`${f === 'unite' ? '' : 'text-right mono'} ${r.badFields?.has(f) ? 'cell-bad' : ''}`}>
                    {fmt(r.line[f])}
                  </td>
                ))}
                {showStatus && <td>{r.status}</td>}
                {showActions && <td>{r.actions}</td>}
              </tr>
            ),
          )}
        </tbody>
      </table>
    </div>
  );
}

/* ---------------------------------------- comparaison champ par champ */

function fmtField(champ, v) {
  if (champ === 'quantite') return fmtQty(v);
  if (champ === 'tauxRemise') return fmtRate(v);
  return fmtMoney(v);
}

export function AxesTable({ axes, left, right }) {
  return (
    <table className="table table-compact">
      <thead>
        <tr>
          <th>Champ</th>
          <th className="text-right">{left}</th>
          <th className="text-right">{right}</th>
          <th className="text-right">Écart</th>
          <th className="text-right">Tolérance</th>
          <th>Résultat</th>
        </tr>
      </thead>
      <tbody>
        {axes.map((ax) => {
          const st = ax.statut === 'écart' ? 'écart' : ax.statut === 'conforme' ? 'conforme' : 'non_comparable';
          const s = productStatus(st);
          return (
            <tr key={ax.champ} className={ax.statut === 'écart' ? 'row-bad' : ''}>
              <td>{FIELD_LABEL[ax.champ] || ax.champ}</td>
              <td className="text-right mono">{fmtField(ax.champ, ax.valeurReference)}</td>
              <td className="text-right mono">{fmtField(ax.champ, ax.valeurComparee)}</td>
              <td className="text-right mono">
                {ax.ecart_signe !== undefined && ax.ecart_signe !== null
                  ? fmtSigned(ax.ecart_signe, (v) => fmtField(ax.champ, v))
                  : '—'}
              </td>
              <td className="text-right mono text-muted">
                {ax.tolerance !== null && ax.tolerance !== undefined ? `± ${fmtField(ax.champ, ax.tolerance)}` : '—'}
              </td>
              <td>
                <Badge tone={s.tone}>{s.label}</Badge>
                {ax.nature && <span className="axis-nature">{NATURE_LABEL[ax.nature] || ax.nature}</span>}
                {ax.motif && <span className="axis-motif">{ax.motif}</span>}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

/* ------------------------------------------------ fenêtre de correction */

export function CorrectionModal({ target, onClose, onSubmit }) {
  const [values, setValues] = useState({});
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (!target) return;
    const init = {};
    for (const f of EDITABLE_FIELDS) init[f] = target.line?.[f] ?? '';
    setValues(init);
    setErrors({});
  }, [target]);

  if (!target) return null;
  const meta = DOC[target.type];

  function submit() {
    const errs = {};
    const changed = {};
    for (const f of EDITABLE_FIELDS) {
      const before = String(target.line?.[f] ?? '');
      const after = String(values[f] ?? '').trim();
      if (after === before.trim()) continue;
      const err = validateField(f, after);
      if (err) errs[f] = err;
      changed[f] = after;
    }
    setErrors(errs);
    if (Object.keys(errs).length) return;
    if (!Object.keys(changed).length) {
      onClose();
      return;
    }
    onSubmit(changed);
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Corriger la ligne ${target.origin + 1} — ${meta?.label}`}
      subtitle="Saisissez la valeur telle qu'imprimée sur le document. Le contrôle arithmétique et la comparaison seront recalculés à l'enregistrement."
      width={640}
      footer={
        <>
          <Button onClick={onClose}>Annuler</Button>
          <Button variant="primary" onClick={submit}>
            Ajouter la correction
          </Button>
        </>
      }
    >
      <div className="form-grid">
        {EDITABLE_FIELDS.map((f) => (
          <label key={f} className={`field ${f === 'designation' ? 'field-wide' : ''}`}>
            <span className="field-label">{FIELD_LABEL[f]}</span>
            <input
              value={values[f] ?? ''}
              onChange={(e) => setValues((v) => ({ ...v, [f]: e.target.value }))}
              className={errors[f] ? 'input-error' : ''}
              inputMode={['quantite', 'prixUnitaireHT', 'tauxRemise', 'montantHT'].includes(f) ? 'decimal' : undefined}
            />
            {errors[f] && <span className="field-error">{errors[f]}</span>}
          </label>
        ))}
      </div>
      <p className="text-muted small">
        Laisser un champ vide l'efface. La quantité doit être un nombre entier ; la remise est comprise entre 0 et 100.
      </p>
    </Modal>
  );
}
