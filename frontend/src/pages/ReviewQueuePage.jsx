import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, CheckCircle2, ClipboardCheck } from 'lucide-react';

import { listAnalyses } from '../api/client.js';
import { useAsync } from '../lib/useAsync.js';
import { fmtDateTime, fmtRelative } from '../lib/format.js';

import { PageHeader, Card } from '../components/ui/Card.jsx';
import Button from '../components/ui/Button.jsx';
import { Badge, DocSet } from '../components/ui/Badge.jsx';
import { ConfidenceMeter } from '../components/ui/Widgets.jsx';
import { EmptyState, ErrorState, LoadingBlock } from '../components/ui/Feedback.jsx';

export default function ReviewQueuePage() {
  const navigate = useNavigate();
  const { data, error, loading, reload } = useAsync(() => listAnalyses(), []);

  // Les plus anciennes d'abord : elles attendent depuis le plus longtemps.
  const queue = useMemo(
    () =>
      (data || [])
        .filter((a) => a.statut === 'en attente de révision')
        .sort((a, b) => new Date(a.date) - new Date(b.date)),
    [data],
  );

  return (
    <div className="page">
      <PageHeader
        eyebrow="Analyses"
        title="File de révision"
        subtitle="Analyses dont un rapprochement ou un contrôle arithmétique attend une décision humaine."
      />

      <Card padded={false}>
        {error ? (
          <div className="card-body"><ErrorState error={error} onRetry={reload} /></div>
        ) : loading && !data ? (
          <LoadingBlock />
        ) : !queue.length ? (
          <EmptyState
            icon={CheckCircle2}
            title="Aucune analyse en attente"
            text="Toutes les analyses ont été tranchées."
          />
        ) : (
          <table className="table table-hover">
            <thead>
              <tr>
                <th className="col-id">N°</th>
                <th>Fichier</th>
                <th>Pièces</th>
                <th>Déposée</th>
                <th>À trancher</th>
                <th>Écarts</th>
                <th>Confiance</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {queue.map((a) => (
                <tr key={a.id} onClick={() => navigate(`/app/analyses/${a.id}?onglet=revision`)}>
                  <td className="mono text-muted">#{a.id}</td>
                  <td className="cell-strong cell-ellipsis" title={a.fichier}>{a.fichier}</td>
                  <td><DocSet types={a.documents} /></td>
                  <td className="text-muted nowrap" title={fmtDateTime(a.date)}>{fmtRelative(a.date)}</td>
                  <td>
                    {a.totaux?.ambigus ? (
                      <Badge tone="warn">{a.totaux.ambigus} rapprochement{a.totaux.ambigus > 1 ? 's' : ''}</Badge>
                    ) : (
                      <Badge tone="warn">Contrôle arithmétique</Badge>
                    )}
                  </td>
                  <td className="mono">{a.totaux?.ecarts ?? '—'}</td>
                  <td><ConfidenceMeter value={a.confiance} compact /></td>
                  <td className="text-right">
                    <Button size="sm" variant="ghost" icon={ArrowRight}>
                      Traiter
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <div className="note note-inline">
        <ClipboardCheck size={16} />
        Une analyse passe « à réviser » quand un rapprochement est ambigu ou qu'un document n'a pas
        pu être certifié arithmétiquement. Les décisions sont rejouées par le moteur : rien n'est
        modifié à la main dans le résultat.
      </div>
    </div>
  );
}
