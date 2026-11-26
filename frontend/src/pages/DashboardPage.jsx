import { useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ClipboardCheck,
  FileStack,
  Plus,
  TrendingUp,
} from 'lucide-react';

import { getStats, listAnalyses } from '../api/client.js';
import { useAuth } from '../context/AuthContext.jsx';
import { useAsync } from '../lib/useAsync.js';
import { analysisStatus } from '../lib/status.js';
import { fmtDateTime, fmtRelative } from '../lib/format.js';

import { Card } from '../components/ui/Card.jsx';
import Button from '../components/ui/Button.jsx';
import { AnalysisStatusBadge, DocSet } from '../components/ui/Badge.jsx';
import { KpiCard, StackBar, ConfidenceMeter } from '../components/ui/Widgets.jsx';
import { EmptyState, ErrorState, LoadingBlock } from '../components/ui/Feedback.jsx';
import ActivityChart from '../components/charts/ActivityChart.jsx';

const DIST = [
  { key: 'ok', label: 'Conformes', tone: 'ok' },
  { key: 'gaps', label: 'Avec écarts', tone: 'err' },
  { key: 'review', label: 'À réviser', tone: 'warn' },
  { key: 'scope', label: 'Hors périmètre', tone: 'muted' },
];

function greeting() {
  const h = new Date().getHours();
  return h < 18 ? 'Bonjour' : 'Bonsoir';
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const stats = useAsync(() => getStats(), []);
  const list = useAsync(() => listAnalyses(), []);

  const distribution = useMemo(() => {
    const counts = { ok: 0, gaps: 0, review: 0, scope: 0 };
    for (const a of list.data || []) {
      const k = analysisStatus(a).key;
      if (k in counts) counts[k] += 1;
    }
    return DIST.map((d) => ({ ...d, value: counts[d.key] }));
  }, [list.data]);

  const queue = useMemo(
    () => (list.data || []).filter((a) => a.statut === 'en attente de révision').slice(0, 5),
    [list.data],
  );

  const s = stats.data;

  return (
    <div className="page">
      <section className="welcome">
        <div>
          <div className="eyebrow">Tableau de bord</div>
          <h1>{greeting()}{user?.nom ? `, ${user.nom.split(/\s+/)[0]}` : ''}</h1>
          <p>
            {s?.a_reviser
              ? `${s.a_reviser} analyse${s.a_reviser > 1 ? 's attendent' : ' attend'} votre décision. Le reste est sous contrôle.`
              : 'Suivez vos contrôles de cohérence entre commandes, livraisons et factures.'}
          </p>
        </div>
        <div className="welcome-actions">
          {s?.a_reviser > 0 && (
            <Button icon={ClipboardCheck} onClick={() => navigate('/app/revisions')}>
              Traiter les révisions
            </Button>
          )}
          <Button variant="primary" icon={Plus} onClick={() => navigate('/app/analyses/nouvelle')}>
            Nouvelle analyse
          </Button>
        </div>
      </section>

      {stats.error ? (
        <ErrorState error={stats.error} onRetry={stats.reload} />
      ) : !s ? (
        <LoadingBlock />
      ) : (
        <>
          <div className="kpi-grid">
            <KpiCard
              label="Analyses réalisées"
              value={s.total}
              icon={FileStack}
              hint={
                <>
                  <b className="text-ok">+{s.cette_semaine}</b> cette semaine
                </>
              }
            />
            <KpiCard
              label="En attente de révision"
              value={s.a_reviser}
              tone={s.a_reviser ? 'warn' : 'neutral'}
              icon={ClipboardCheck}
              hint="Rapprochements à trancher"
              onClick={() => navigate('/app/revisions')}
            />
            <KpiCard
              label="Taux de conformité"
              value={s.pct_conformes ?? '—'}
              unit={s.pct_conformes === null ? '' : '%'}
              tone="ok"
              icon={CheckCircle2}
              hint={`${s.conformes} / ${s.produits} produits conformes`}
            />
            <KpiCard
              label="Écarts ce mois"
              value={s.ecarts_mois}
              tone={s.ecarts_mois ? 'err' : 'neutral'}
              icon={AlertTriangle}
              hint={
                <>
                  dont <b>{s.ecarts_prix_mois}</b> écart{s.ecarts_prix_mois > 1 ? 's' : ''} de prix
                </>
              }
            />
          </div>

          <div className="grid-2-1">
            <Card
              title="Activité des 8 dernières semaines"
              icon={TrendingUp}
              actions={
                <div className="legend">
                  <span><i className="legend-a" />Analyses</span>
                  <span><i className="legend-b" />Avec écarts</span>
                </div>
              }
            >
              <ActivityChart weeks={s.activite} />
            </Card>

            <Card title="Répartition des analyses" subtitle={`${(list.data || []).length} analyses enregistrées`}>
              <StackBar segments={distribution} height={12} />
              <ul className="dist-list">
                {distribution.map((d) => (
                  <li key={d.key}>
                    <span className={`dist-dot seg-${d.tone}`} />
                    <span className="dist-label">{d.label}</span>
                    <span className="dist-value">{d.value}</span>
                  </li>
                ))}
              </ul>
            </Card>
          </div>

          <div className="grid-2-1">
            <Card
              title="Dernières analyses"
              padded={false}
              actions={
                <Link to="/app/analyses" className="link">
                  Tout l'historique <ArrowRight size={14} />
                </Link>
              }
            >
              {s.recentes.length ? (
                <table className="table table-hover">
                  <thead>
                    <tr>
                      <th>Fichier</th>
                      <th>Pièces</th>
                      <th>Date</th>
                      <th>Confiance</th>
                      <th>Statut</th>
                    </tr>
                  </thead>
                  <tbody>
                    {s.recentes.map((a) => (
                      <tr key={a.id} onClick={() => navigate(`/app/analyses/${a.id}`)}>
                        <td className="cell-strong cell-ellipsis">{a.fichier}</td>
                        <td><DocSet types={a.documents} /></td>
                        <td className="text-muted">{fmtDateTime(a.date)}</td>
                        <td><ConfidenceMeter value={a.confiance} compact /></td>
                        <td><AnalysisStatusBadge analysis={a} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <EmptyState
                  title="Aucune analyse"
                  text="Déposez un premier PDF pour lancer un contrôle."
                  action={
                    <Button variant="primary" icon={Plus} onClick={() => navigate('/app/analyses/nouvelle')}>
                      Nouvelle analyse
                    </Button>
                  }
                />
              )}
            </Card>

            <Card
              title="File de révision"
              subtitle="Analyses qui attendent une décision"
              padded={false}
              actions={
                <Link to="/app/revisions" className="link">
                  Tout voir <ArrowRight size={14} />
                </Link>
              }
            >
              {queue.length ? (
                <ul className="queue">
                  {queue.map((a) => (
                    <li key={a.id} onClick={() => navigate(`/app/analyses/${a.id}?onglet=revision`)}>
                      <div>
                        <strong className="cell-ellipsis">{a.fichier}</strong>
                        <small>{fmtRelative(a.date)} · {a.totaux?.ambigus ?? 0} à trancher</small>
                      </div>
                      <ArrowRight size={15} />
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState icon={CheckCircle2} title="Rien à réviser" text="Toutes les analyses sont tranchées." />
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
