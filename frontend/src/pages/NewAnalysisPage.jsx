import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowRight,
  Check,
  FileText,
  Info,
  RotateCcw,
  UploadCloud,
} from 'lucide-react';

import { getJob, uploadAnalysis } from '../api/client.js';
import { useToast } from '../context/ToastContext.jsx';
import { fmtBytes } from '../lib/format.js';

import { PageHeader, Card } from '../components/ui/Card.jsx';
import Button from '../components/ui/Button.jsx';
import { Spinner } from '../components/ui/Feedback.jsx';

const MAX_BYTES = 20 * 1024 * 1024;
const JOB_KEY = 'concordance.job';

// Les cinq étapes publiées par le backend (webapp/jobs.py).
const STEPS = [
  { title: 'Lecture du document', text: 'Découpage, rendu des pages, prétraitement des scans' },
  { title: 'Identification des pages', text: 'Bon de commande, bon de livraison, facture' },
  { title: 'Extraction des données', text: 'En-têtes, lignes de produits, totaux' },
  { title: 'Contrôle et validation', text: 'Cohérence arithmétique des montants' },
  { title: 'Comparaison des documents', text: 'Rapprochement ligne à ligne' },
];

/* Explication des erreurs du modèle, sans toucher au message d'origine. */
function errorHint(msg = '') {
  if (msg.includes('429') || msg.includes('RESOURCE_EXHAUSTED')) {
    return "Le quota de l'API Gemini est épuisé pour ce modèle. Attendez la réinitialisation, changez GEMINI_MODEL dans .env ou activez la facturation du projet Google.";
  }
  if (msg.includes('503') || msg.includes('UNAVAILABLE')) {
    return 'Le modèle Gemini est momentanément saturé chez Google. Réessayez dans quelques minutes ou choisissez un autre modèle (GEMINI_MODEL).';
  }
  if (msg.includes('GEMINI_API_KEY')) return 'La clé GEMINI_API_KEY est absente du fichier .env.';
  return null;
}

function useElapsed(since) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!since) return undefined;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [since]);
  if (!since) return null;
  const s = Math.max(0, Math.floor((now - since) / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

export default function NewAnalysisPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const inputRef = useRef(null);

  // idle | uploading | running | done | failed
  const [phase, setPhase] = useState('idle');
  const [file, setFile] = useState(null);
  const [job, setJob] = useState(null);
  const [error, setError] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [startedAt, setStartedAt] = useState(null);
  const elapsed = useElapsed(phase === 'running' || phase === 'uploading' ? startedAt : null);

  /* Reprise d'un traitement en cours après un changement de page. */
  useEffect(() => {
    const saved = sessionStorage.getItem(JOB_KEY);
    if (!saved) return;
    try {
      const { id, name, size, started } = JSON.parse(saved);
      setFile({ name, size });
      setJob({ id, etape: 0, detail: 'Reprise du suivi…' });
      setStartedAt(started);
      setPhase('running');
    } catch {
      sessionStorage.removeItem(JOB_KEY);
    }
  }, []);

  /* Sondage de la progression. */
  useEffect(() => {
    if (phase !== 'running' || !job?.id) return undefined;
    let stop = false;
    let timer;
    const tick = async () => {
      try {
        const j = await getJob(job.id);
        if (stop) return;
        setJob(j);
        if (j.statut === 'terminé') {
          sessionStorage.removeItem(JOB_KEY);
          setPhase('done');
          if (j.resume?.status === 'hors périmètre') toast.error('Document hors périmètre — voir le détail');
          else toast.success('Analyse terminée');
          if (j.id_analyse) setTimeout(() => navigate(`/app/analyses/${j.id_analyse}`), 900);
          return;
        }
        if (j.statut === 'erreur') {
          sessionStorage.removeItem(JOB_KEY);
          setError(j.erreur || 'Le traitement a échoué');
          setPhase('failed');
          return;
        }
      } catch (e) {
        if (stop) return;
        // 404 : le serveur a redémarré, le suivi en mémoire est perdu
        sessionStorage.removeItem(JOB_KEY);
        setError(e.status === 404 ? 'Suivi perdu (le serveur a redémarré). Consultez l’historique.' : e.message);
        setPhase('failed');
        return;
      }
      timer = setTimeout(tick, 1500);
    };
    tick();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [phase, job?.id, navigate, toast]);

  const start = useCallback(
    async (f) => {
      if (!f) return;
      if (f.type !== 'application/pdf' && !f.name.toLowerCase().endsWith('.pdf')) {
        toast.error('Seul un document PDF est accepté');
        return;
      }
      if (f.size > MAX_BYTES) {
        toast.error('Fichier trop volumineux (20 Mo maximum)');
        return;
      }
      setFile({ name: f.name, size: f.size });
      setError('');
      setPhase('uploading');
      const started = Date.now();
      setStartedAt(started);
      try {
        const res = await uploadAnalysis(f);
        sessionStorage.setItem(JOB_KEY, JSON.stringify({ id: res.job, name: f.name, size: f.size, started }));
        setJob({ id: res.job, etape: 0, detail: "En file d'attente…" });
        setPhase('running');
      } catch (e) {
        setError(e.message);
        setPhase('failed');
      }
    },
    [toast],
  );

  function reset() {
    sessionStorage.removeItem(JOB_KEY);
    setPhase('idle');
    setFile(null);
    setJob(null);
    setError('');
  }

  const current = job?.etape || 0;
  const stepState = (i) => {
    const n = i + 1;
    if (phase === 'done' || n < current) return 'done';
    if (phase === 'failed' && n === Math.max(current, 1)) return 'failed';
    if (n === current || (current === 0 && n === 1 && phase !== 'failed')) return 'active';
    return 'pending';
  };
  const hint = errorHint(error);

  return (
    <div className="page">
      <PageHeader
        eyebrow="Analyses"
        title="Nouvelle analyse"
        subtitle="Déposez un PDF regroupant le bon de commande et au moins un bon de livraison ou une facture."
      />

      <div className="grid-2-1">
        <div className="stack">
          {phase === 'idle' ? (
            <div
              className={`dropzone ${dragOver ? 'dropzone-over' : ''}`}
              onClick={() => inputRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                start(e.dataTransfer.files?.[0]);
              }}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
            >
              <input
                ref={inputRef}
                type="file"
                accept="application/pdf"
                hidden
                onChange={(e) => {
                  start(e.target.files?.[0]);
                  e.target.value = '';
                }}
              />
              <span className="dropzone-icon">
                <UploadCloud size={28} />
              </span>
              <h3>Glissez votre PDF ici</h3>
              <p>
                ou <span className="link">parcourez vos dossiers</span>
              </p>
              <span className="dropzone-hint">Un seul fichier PDF · natif ou scanné · 20 Mo maximum</span>
            </div>
          ) : (
            <Card
              title={phase === 'done' ? 'Analyse terminée' : phase === 'failed' ? 'Échec du traitement' : 'Analyse en cours'}
              actions={elapsed && <span className="elapsed">{elapsed}</span>}
            >
              <div className="filechip">
                <FileText size={18} />
                <div>
                  <strong>{file?.name}</strong>
                  <small>{fmtBytes(file?.size)}</small>
                </div>
              </div>

              <ol className="stepper">
                {STEPS.map((s, i) => {
                  const st = stepState(i);
                  return (
                    <li key={s.title} className={`step step-${st}`}>
                      <span className="step-marker">
                        {st === 'done' ? (
                          <Check size={14} />
                        ) : st === 'active' ? (
                          <Spinner size={14} />
                        ) : st === 'failed' ? (
                          <AlertTriangle size={14} />
                        ) : (
                          i + 1
                        )}
                      </span>
                      <div className="step-body">
                        <strong>{s.title}</strong>
                        <span>{st === 'active' && job?.detail ? job.detail : s.text}</span>
                      </div>
                    </li>
                  );
                })}
              </ol>

              {phase === 'failed' && (
                <div className="alert alert-err">
                  <AlertTriangle size={18} />
                  <div>
                    <strong>Le traitement a échoué</strong>
                    {hint && <p className="alert-hint">{hint}</p>}
                    <details>
                      <summary>Message technique</summary>
                      <code className="alert-code">{error}</code>
                    </details>
                  </div>
                </div>
              )}

              <div className="card-footer-actions">
                {phase === 'failed' && (
                  <Button icon={RotateCcw} onClick={reset}>
                    Déposer un autre fichier
                  </Button>
                )}
                {phase === 'done' && job?.id_analyse && (
                  <Button variant="primary" icon={ArrowRight} onClick={() => navigate(`/app/analyses/${job.id_analyse}`)}>
                    Voir le résultat
                  </Button>
                )}
                {(phase === 'running' || phase === 'uploading') && (
                  <span className="text-muted small">
                    Vous pouvez quitter cette page : le traitement continue sur le serveur.
                  </span>
                )}
              </div>
            </Card>
          )}
        </div>

        <Card title="Avant de déposer" icon={Info}>
          <ul className="checklist">
            <li>
              <Check size={15} />
              <span><b>Un bon de commande</b> est obligatoire : c'est la référence de toutes les comparaisons.</span>
            </li>
            <li>
              <Check size={15} />
              <span>Au moins <b>un bon de livraison ou une facture</b> dans le même PDF.</span>
            </li>
            <li>
              <Check size={15} />
              <span>Les pages scannées sont redressées et nettoyées automatiquement.</span>
            </li>
            <li>
              <Check size={15} />
              <span>Toute page non reconnue place l'analyse <b>hors périmètre</b>.</span>
            </li>
          </ul>
          <div className="note">
            Durée indicative : 1 à 3 minutes selon le nombre de pages. Chaque page et chaque
            document font l'objet d'un appel au modèle d'extraction.
          </div>
        </Card>
      </div>
    </div>
  );
}
