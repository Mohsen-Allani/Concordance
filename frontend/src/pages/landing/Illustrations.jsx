/* Illustrations de la page d'accueil, dessinées en HTML/CSS/SVG.
 * Les données affichées reprennent le scénario de test du projet
 * (tests/data.py) : vis VIS-1240, cadenas 2110160, tube TC-14. */
import {
  AlertTriangle,
  Check,
  Clock,
  FileQuestion,
  HelpCircle,
  ScanLine,
  X,
} from 'lucide-react';

const TAG = { BC: 'bc', BL: 'bl', FA: 'fa' };
const LABEL = { BC: 'Bon de commande', BL: 'Bon de livraison', FA: 'Facture' };

/* ------------------------------------------------------- pièce papier */
export function DocPaper({ type, number, rows, total, className = '', style }) {
  return (
    <div className={`paper paper-${TAG[type]} ${className}`} style={style}>
      <div className="paper-head">
        <span className={`doctag doctag-${TAG[type]} doctag-sm`}>{type}</span>
        <span className="paper-title">{LABEL[type]}</span>
      </div>
      <div className="paper-num">N° {number}</div>
      <div className="paper-rows">
        {rows.map((r, i) => (
          <div key={i} className={`paper-row ${r.flag ? `paper-row-${r.flag}` : ''}`}>
            <span className="paper-ref">{r.ref}</span>
            <span className="paper-bar" style={{ width: r.w || '60%' }} />
            <span className="paper-val">{r.val}</span>
          </div>
        ))}
      </div>
      {total && (
        <div className="paper-total">
          <span>Total HT</span>
          <b>{total}</b>
        </div>
      )}
    </div>
  );
}

/* ----------------------------------------------------- carte rapport */
const REPORT_ROWS = [
  { ref: 'VIS-1240', des: 'Vis TH M12x40', tone: 'ok', label: 'Conforme', icon: Check },
  { ref: '2110160', des: 'Cadenas laiton 60 mm', tone: 'err', label: 'Prix +0,600/u', icon: X },
  { ref: '2110160', des: 'Livrés : 20 sur 24', tone: 'err', label: 'Quantité −4', icon: X },
  { ref: 'TC-14', des: 'Tube cuivre D14', tone: 'warn', label: 'Non livré', icon: AlertTriangle },
];

export function ReportCard({ compact = false }) {
  return (
    <div className={`report ${compact ? 'report-compact' : ''}`}>
      <div className="report-head">
        <div>
          <span className="report-kicker">Rapport de concordance</span>
          <strong>BC 2214 · BL L-4471 · FA F2026-412</strong>
        </div>
        <span className="report-score">
          <span>Confiance</span>
          <b>97 %</b>
        </span>
      </div>
      <div className="report-tally">
        <span className="tally tally-ok"><b>1</b> conforme</span>
        <span className="tally tally-err"><b>2</b> écarts</span>
        <span className="tally tally-warn"><b>1</b> manquant</span>
      </div>
      <ul className="report-rows">
        {REPORT_ROWS.slice(0, compact ? 3 : 4).map((r, i) => (
          <li key={i}>
            <span className={`report-ico report-ico-${r.tone}`}>
              <r.icon size={12} strokeWidth={3} />
            </span>
            <span className="report-ref">{r.ref}</span>
            <span className="report-des">{r.des}</span>
            <span className={`report-badge report-badge-${r.tone}`}>{r.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* --------------------------------------------------------- visuel héros */
export function HeroVisual() {
  return (
    <div className="hero-visual" aria-hidden>
      <div className="hero-glow" />
      <div className="hero-papers">
        <DocPaper
          type="BC"
          number="2214"
          className="hero-paper hp-1"
          rows={[
            { ref: 'VIS-1240', val: '200', w: '55%' },
            { ref: '2110160', val: '24', w: '70%' },
            { ref: 'TC-14', val: '6', w: '45%' },
          ]}
          total="432,400"
        />
        <DocPaper
          type="BL"
          number="L-4471"
          className="hero-paper hp-2"
          rows={[
            { ref: 'VIS-1240', val: '200', w: '50%' },
            { ref: '2110160', val: '20', w: '62%', flag: 'err' },
          ]}
        />
        <DocPaper
          type="FA"
          number="F2026-412"
          className="hero-paper hp-3"
          rows={[
            { ref: 'VIS-1240', val: '0,185', w: '52%' },
            { ref: '2110160', val: '12,500', w: '66%', flag: 'err' },
          ]}
          total="337,000"
        />
      </div>

      <svg className="hero-links" viewBox="0 0 200 300" preserveAspectRatio="none">
        <path d="M0 50 C 100 50, 90 150, 200 150" />
        <path d="M0 150 C 100 150, 100 150, 200 150" />
        <path d="M0 250 C 100 250, 90 150, 200 150" />
      </svg>

      <div className="hero-report">
        <ReportCard />
      </div>

      <div className="hero-float hf-1">
        <span className="hf-dot hf-dot-err" />
        Écart de prix détecté
        <b>+0,600 TND/u</b>
      </div>
      <div className="hero-float hf-2">
        <ScanLine size={14} />
        Scan redressé et nettoyé
      </div>
    </div>
  );
}

/* --------------------------------------------- visuel de la problématique */
export function ProblemVisual() {
  return (
    <div className="problem-visual" aria-hidden>
      <DocPaper
        type="BC"
        number="2214"
        className="pv-paper pv-1"
        rows={[
          { ref: 'Réf. 2110160', val: '24 × 11,900', w: '40%', flag: 'mark' },
          { ref: 'TC-14', val: '6 × 18,300', w: '55%' },
        ]}
      />
      <DocPaper
        type="BL"
        number="L-4471"
        className="pv-paper pv-2"
        rows={[
          { ref: 'CADENAS 60MM', val: '20', w: '35%', flag: 'err' },
          { ref: 'VIS M12x40', val: '200', w: '45%' },
        ]}
      />
      <DocPaper
        type="FA"
        number="F2026-412"
        className="pv-paper pv-3 pv-scan"
        rows={[
          { ref: 'supp. 2110160', val: '24 × 12,500', w: '38%', flag: 'err' },
          { ref: 'VIS TH GAL', val: '200 × 0,185', w: '50%' },
        ]}
      />
      <span className="pv-neq pv-neq-1">≠</span>
      <span className="pv-neq pv-neq-2">≠</span>
      <div className="pv-note pv-note-1">
        <FileQuestion size={15} /> « supp », « fournisseur », « supplier » ?
      </div>
      <div className="pv-note pv-note-2">
        <Clock size={15} /> Vérification ligne à ligne, à la main
      </div>
      <div className="pv-note pv-note-3">
        <HelpCircle size={15} /> Livré 20, facturé 24 ?
      </div>
    </div>
  );
}

/* ----------------------------------------------- aperçu de l'application */
const PREVIEW_ROWS = [
  { tone: 'ok', label: 'Conforme', ref: 'VIS-1240', des: 'VIS TH GAL CL 8.8 M12x40', q: ['200', '200', '200'], note: 'Quantités et prix concordants' },
  { tone: 'err', label: 'Écart', ref: '2110160', des: 'CADENAS BLOCUS LAITON 60 MM', q: ['24', '20', '24'], note: 'BL : 20 sur 24 · FA : +0,600 par unité' },
  { tone: 'err', label: 'Manquant', ref: 'TC-14', des: 'TUBE CUIVRE D14 barre 4 m', q: ['6', '·', '·'], note: 'Non livré · Non facturé' },
];

export function AppPreview() {
  return (
    <div className="preview" aria-hidden>
      <div className="preview-bar">
        <span className="preview-dots">
          <i />
          <i />
          <i />
        </span>
        <span className="preview-url">concordance · analyses · n° 12</span>
      </div>
      <div className="preview-body">
        <div className="preview-title">
          <div>
            <small>BC-2214_quincaillerie.pdf</small>
            <strong>2 écarts détectés</strong>
          </div>
          <span className="preview-btn">Rapport PDF</span>
        </div>
        <div className="preview-kpis">
          <div><small>Produits</small><b>3</b></div>
          <div className="pk-ok"><small>Conformes</small><b>1</b></div>
          <div className="pk-err"><small>Écarts</small><b>2</b></div>
          <div className="pk-warn"><small>À trancher</small><b>0</b></div>
        </div>
        <div className="preview-tabs">
          <span>Synthèse</span>
          <span className="on">Rapprochement</span>
          <span>Montants</span>
          <span>Documents</span>
          <span>Révision</span>
        </div>
        <div className="preview-table">
          <div className="preview-tr preview-th">
            <span>Statut</span>
            <span>Référence</span>
            <span>Désignation</span>
            <span>BC</span>
            <span>BL</span>
            <span>FA</span>
            <span>Constat</span>
          </div>
          {PREVIEW_ROWS.map((r) => (
            <div key={r.ref} className={`preview-tr preview-tr-${r.tone}`}>
              <span><i className={`preview-badge pb-${r.tone}`}>{r.label}</i></span>
              <span className="mono">{r.ref}</span>
              <span className="preview-des">{r.des}</span>
              {r.q.map((v, i) => (
                <span key={i} className={`mono ${r.tone === 'err' && v !== r.q[0] ? 'preview-bad' : ''}`}>{v}</span>
              ))}
              <span className="preview-note">{r.note}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
