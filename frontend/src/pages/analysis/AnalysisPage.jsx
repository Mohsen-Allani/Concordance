import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  ClipboardCheck,
  Coins,
  Download,
  FileText,
  GitCompareArrows,
  LayoutGrid,
  RefreshCw,
  Undo2,
} from 'lucide-react';

import { downloadReport, getAnalysis, saveRevisions } from '../../api/client.js';
import { useAsync } from '../../lib/useAsync.js';
import { useToast } from '../../context/ToastContext.jsx';
import { fmtDateTime } from '../../lib/format.js';
import { DOC_TYPES } from '../../lib/status.js';
import { replay, touchedLines } from '../../lib/revisions.js';

import Button from '../../components/ui/Button.jsx';
import Tabs from '../../components/ui/Tabs.jsx';
import { AnalysisStatusBadge, DocSet } from '../../components/ui/Badge.jsx';
import { ConfidenceMeter } from '../../components/ui/Widgets.jsx';
import { ErrorState, LoadingBlock, Spinner } from '../../components/ui/Feedback.jsx';

import { CorrectionModal } from './shared.jsx';
import SummaryTab from './SummaryTab.jsx';
import MatchingTab from './MatchingTab.jsx';
import AmountsTab from './AmountsTab.jsx';
import DocumentsTab from './DocumentsTab.jsx';
import ReviewTab from './ReviewTab.jsx';

export default function AnalysisPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const tab = params.get('onglet') || 'synthese';
  const setTab = useCallback(
    (k, extra = {}) => setParams({ onglet: k, ...extra }, { replace: true }),
    [setParams],
  );

  const { data: analysis, error, loading, reload, setData } = useAsync(() => getAnalysis(id), [id]);

  const [ops, setOps] = useState([]);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [correction, setCorrection] = useState(null);

  useEffect(() => {
    setOps([]);
  }, [id]);

  // Prévenir la perte de révisions non enregistrées.
  useEffect(() => {
    if (!ops.length) return undefined;
    const warn = (e) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [ops.length]);

  const addOp = useCallback(
    (op) => {
      setOps((o) => [...o, { ...op, id: `${Date.now()}-${Math.random()}` }]);
      toast.success('Modification ajoutée — enregistrez pour recalculer');
    },
    [toast],
  );
  const removeOp = useCallback((opId) => setOps((o) => o.filter((x) => x.id !== opId)), []);

  const revState = useMemo(() => (analysis ? replay(analysis, ops) : null), [analysis, ops]);
  const touched = useMemo(() => touchedLines(ops), [ops]);

  async function apply(message) {
    setSaving(true);
    try {
      const updated = await saveRevisions(analysis.id, revState);
      setData(updated);
      setOps([]);
      toast.success(message);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function onDownload() {
    setDownloading(true);
    try {
      await downloadReport(analysis.id, analysis.fichier);
      toast.success('Rapport PDF téléchargé');
    } catch (e) {
      toast.error(e.message);
    } finally {
      setDownloading(false);
    }
  }

  if (error) {
    return (
      <div className="page">
        <ErrorState error={error} onRetry={reload} />
      </div>
    );
  }
  if (loading && !analysis) return <LoadingBlock label="Chargement de l'analyse…" />;

  const c = analysis.comparaison;
  const comparable = c && c.statut !== 'impossible';
  const ambiguities = (c?.ambiguites || []).length;
  const toReview = (analysis.documents_detail || []).filter((d) => d.verdict === 'review').length;
  const ctx = {
    analysis,
    comparison: c,
    ops,
    addOp,
    removeOp,
    touched,
    savedCorrections: analysis.revisions?.corrections || {},
    openCorrection: setCorrection,
    goTab: setTab,
  };

  const tabs = [
    { key: 'synthese', label: 'Synthèse', icon: LayoutGrid },
    { key: 'rapprochement', label: 'Rapprochement', icon: GitCompareArrows, count: c?.totaux?.produits, disabled: !comparable },
    { key: 'montants', label: 'Montants', icon: Coins, disabled: !comparable },
    { key: 'documents', label: 'Documents', icon: FileText, count: (analysis.documents_detail || []).length || undefined },
    {
      key: 'revision',
      label: 'Révision',
      icon: ClipboardCheck,
      count: ambiguities + toReview + ops.length || undefined,
      countTone: ambiguities || toReview ? 'warn' : ops.length ? 'edit' : undefined,
      disabled: !comparable,
    },
  ];
  const activeTab = tabs.find((t) => t.key === tab && !t.disabled) ? tab : 'synthese';

  return (
    <div className="page page-analysis">
      <div className="analysis-head">
        <button className="back-link" onClick={() => navigate('/app/analyses')}>
          <ArrowLeft size={15} /> Historique
        </button>
        <div className="analysis-title-row">
          <div className="analysis-title">
            <h1 title={analysis.fichier}>{analysis.fichier}</h1>
            <div className="analysis-meta">
              <span className="mono">#{analysis.id}</span>
              <span>{fmtDateTime(analysis.date)}</span>
              <span>{analysis.pages ?? '?'} page{analysis.pages > 1 ? 's' : ''}</span>
              <DocSet types={DOC_TYPES.filter((t) => (analysis.documents || []).includes(t))} />
              <AnalysisStatusBadge analysis={analysis} />
              <span className="meta-conf">
                Confiance <ConfidenceMeter value={analysis.confiance} compact />
              </span>
            </div>
          </div>
          <div className="page-actions">
            {comparable && (
              <Button
                icon={RefreshCw}
                loading={saving && !ops.length}
                onClick={() => apply('Analyse rejouée à l’identique')}
                title={
                  ops.length
                    ? 'Enregistrez ou annulez d’abord les modifications en attente'
                    : 'Rejoue normalisation, validation et comparaison sans appeler le modèle'
                }
                disabled={saving || ops.length > 0}
              >
                Rejouer
              </Button>
            )}
            {analysis.rapport && (
              <Button variant="primary" icon={Download} loading={downloading} onClick={onDownload}>
                Rapport PDF
              </Button>
            )}
          </div>
        </div>
        <Tabs tabs={tabs} value={activeTab} onChange={(k) => setTab(k)} />
      </div>

      <div className="analysis-body">
        {activeTab === 'synthese' && <SummaryTab ctx={ctx} />}
        {activeTab === 'rapprochement' && <MatchingTab ctx={ctx} />}
        {activeTab === 'montants' && <AmountsTab ctx={ctx} />}
        {activeTab === 'documents' && <DocumentsTab ctx={ctx} />}
        {activeTab === 'revision' && <ReviewTab ctx={ctx} />}
      </div>

      {ops.length > 0 && (
        <div className="applybar">
          <div className="applybar-msg">
            <span className="applybar-count">{ops.length}</span>
            modification{ops.length > 1 ? 's' : ''} en attente
            {activeTab !== 'revision' && (
              <button className="link" onClick={() => setTab('revision')}>
                Voir le détail
              </button>
            )}
          </div>
          <div className="applybar-actions">
            <Button icon={Undo2} onClick={() => setOps([])} disabled={saving}>
              Tout annuler
            </Button>
            <Button
              variant="primary"
              icon={RefreshCw}
              loading={saving}
              onClick={() => apply('Comparaison recalculée — rapport PDF régénéré')}
            >
              Enregistrer et recalculer
            </Button>
          </div>
        </div>
      )}

      {saving && (
        <div className="overlay">
          <div className="overlay-box">
            <Spinner size={22} />
            <span>Rapprochement rejoué sous vos révisions…</span>
          </div>
        </div>
      )}

      <CorrectionModal
        target={correction}
        onClose={() => setCorrection(null)}
        onSubmit={(fields) => {
          addOp({ kind: 'correct', doc: correction.type, origin: correction.origin, fields });
          setCorrection(null);
        }}
      />
    </div>
  );
}
