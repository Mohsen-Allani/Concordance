import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowDown,
  ArrowRight,
  BadgeCheck,
  Brain,
  Calculator,
  Clock,
  Cpu,
  Database,
  Eye,
  FileCheck2,
  FileStack,
  FileText,
  Fingerprint,
  GitCompareArrows,
  Hand,
  Layers,
  ListChecks,
  RefreshCcw,
  Ruler,
  ScanLine,
  Scale,
  ShieldAlert,
  Shuffle,
  Sparkles,
  UserCheck,
  Wand2,
} from 'lucide-react';

import { useAuth } from '../../context/AuthContext.jsx';
import Logo from '../../components/brand/Logo.jsx';
import { AppPreview, HeroVisual, ProblemVisual } from './Illustrations.jsx';
import { useReveal } from './useReveal.js';

const SECTIONS = [
  { id: 'problematique', label: 'Problématique' },
  { id: 'solution', label: 'Solution' },
  { id: 'fonctionnement', label: 'Fonctionnement' },
  { id: 'resultats', label: 'Résultats' },
  { id: 'fonctionnalites', label: 'Fonctionnalités' },
];

const FACTS = [
  { value: '3', label: 'pièces rapprochées', sub: 'BC · BL · Facture' },
  { value: '10', label: 'étapes de traitement', sub: 'de L0 à L9' },
  { value: '2', label: 'étapes seulement', sub: 'font appel à l’IA' },
  { value: '100 %', label: 'des calculs rejouables', sub: 'sans nouvel appel au modèle' },
];

const PAINS = [
  {
    icon: Clock,
    title: 'Un contrôle manuel, ligne à ligne',
    text: 'Chaque commande, livraison et facture est relue et recoupée à la main : un travail lent et répétitif.',
  },
  {
    icon: Shuffle,
    title: 'Des formats qui ne s’accordent jamais',
    text: 'Chaque fournisseur a sa mise en page et ses libellés : « supp », « supplier », « fournisseur »…',
  },
  {
    icon: ScanLine,
    title: 'Des scans de mauvaise qualité',
    text: 'Pages penchées, bruitées ou peu contrastées : la lecture elle-même devient incertaine.',
  },
  {
    icon: ShieldAlert,
    title: 'Un risque financier réel',
    text: 'Payer une marchandise non livrée, accepter un prix majoré ou une quantité gonflée sans le voir.',
  },
];

const PILLARS = [
  {
    n: '01',
    icon: Eye,
    title: 'Lire',
    text: 'Un modèle de vision (Vision-LLM) transforme chaque page en données structurées, quel que soit le format du fournisseur. Les scans sont redressés et nettoyés avant lecture.',
  },
  {
    n: '02',
    icon: Calculator,
    title: 'Vérifier',
    text: 'Un solveur arithmétique contrôle quantité × prix, remises, TVA et totaux de chaque document. Les tolérances sont déduites de la précision imprimée, jamais fixées à l’avance.',
  },
  {
    n: '03',
    icon: GitCompareArrows,
    title: 'Rapprocher',
    text: 'Chaque ligne livrée et facturée est confrontée au bon de commande, par ordre de preuve : référence exacte, code retrouvé, puis similarité du texte.',
  },
];

const PIPELINE = [
  { layers: 'L0 – L2', icon: FileStack, title: 'Lecture du PDF', text: 'Découpage, rendu des pages à 300 dpi, détection des scans, redressement et débruitage.', ai: false },
  { layers: 'L3 – L4', icon: Brain, title: 'Identification', text: 'Chaque page est reconnue (BC, BL, facture), puis regroupée en documents. Le périmètre est vérifié.', ai: true },
  { layers: 'L5', icon: Wand2, title: 'Extraction', text: 'En-têtes, lignes et totaux extraits en JSON selon un schéma strict. Toute valeur incertaine reste vide.', ai: true },
  { layers: 'L6 – L7', icon: Calculator, title: 'Normalisation et validation', text: 'Montants en décimal exact, dates ISO, puis contrôle arithmétique complet et score de confiance.', ai: false },
  { layers: 'L8', icon: GitCompareArrows, title: 'Rapprochement', text: 'Comparaison BC ↔ BL et BC ↔ Facture, produit par produit et champ par champ.', ai: false },
  { layers: 'L9', icon: FileCheck2, title: 'Rapport et archivage', text: 'Rapport PDF détaillé et historique complet en base PostgreSQL.', ai: false },
];

const OUTCOMES = [
  { tone: 'ok', label: 'Conforme', text: 'Quantités, prix et montants concordent entre les pièces.' },
  { tone: 'err', label: 'Écart de quantité', text: 'Sous-livraison ou sur-livraison, avec la différence exacte.' },
  { tone: 'err', label: 'Écart de prix', text: 'Prix unitaire ou remise facturés différents de la commande.' },
  { tone: 'err', label: 'Manquant', text: 'Commandé, mais ni livré ni facturé.' },
  { tone: 'err', label: 'En trop', text: 'Livré ou facturé sans avoir été commandé.' },
  { tone: 'warn', label: 'À trancher', text: 'Plusieurs lignes possibles : le système refuse de deviner.' },
];

const FEATURES = [
  { icon: Layers, title: 'Indépendant du format', text: 'Les champs sont reconnus par leur rôle dans le document, pas par leur libellé.' },
  { icon: ScanLine, title: 'Traitement des scans', text: 'Redressement, débruitage et amélioration du contraste avec OpenCV.' },
  { icon: Ruler, title: 'Tolérances intelligentes', text: 'Déduites des décimales imprimées : le millime pour le dinar tunisien.' },
  { icon: Fingerprint, title: 'Appariement par preuves', text: 'La rareté d’un code fait sa force ; une égalité n’est jamais tranchée au hasard.' },
  { icon: UserCheck, title: 'Humain dans la boucle', text: 'Corriger une valeur, choisir un candidat, réaffecter ou détacher une ligne.' },
  { icon: FileText, title: 'Rapport et historique', text: 'Rapport PDF par analyse, tableau de bord et historique complet.' },
];

const PRINCIPLES = [
  { icon: RefreshCcw, title: 'Rejouable', text: 'Seule l’extraction coûte un appel au modèle. Tout le reste se rejoue à l’identique, gratuitement.' },
  { icon: Scale, title: 'Le BC fait référence', text: 'Tout est comparé à la commande, jamais BL contre facture : aucune contradiction possible.' },
  { icon: Hand, title: 'Ne jamais deviner', text: 'Une valeur illisible reste vide ; une ambiguïté est signalée, pas tranchée.' },
  { icon: BadgeCheck, title: 'Révisions auditables', text: 'Chaque décision humaine est une contrainte rejouée et archivée.' },
];

const STACK = ['Python', 'FastAPI', 'PostgreSQL', 'SQLAlchemy', 'Gemini Vision', 'OpenCV', 'PyMuPDF', 'WeasyPrint', 'React', 'Vite', 'Docker'];

export default function LandingPage() {
  const { status, user, logout } = useAuth();
  const navigate = useNavigate();
  const rootRef = useRef(null);
  const [scrolled, setScrolled] = useState(false);
  useReveal(rootRef);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const authed = status === 'authenticated';
  const enter = () => navigate(authed ? '/app' : '/connexion');
  const goto = (id) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });

  return (
    <div className="landing" ref={rootRef}>
      {/* ------------------------------------------------------ navigation */}
      <header className={`lnav ${scrolled ? 'lnav-solid' : ''}`}>
        <div className="lnav-inner">
          <button className="lnav-brand" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            <Logo light={!scrolled} size={34} />
          </button>
          <nav className="lnav-links">
            {SECTIONS.map((s) => (
              <button key={s.id} onClick={() => goto(s.id)}>
                {s.label}
              </button>
            ))}
          </nav>
          <div className="lnav-actions">
            {authed ? (
              <button className="lnav-login" onClick={logout} title={user?.email}>
                Se déconnecter
              </button>
            ) : (
              <Link to="/connexion" className="lnav-login">
                Se connecter
              </Link>
            )}
            <button className="lbtn lbtn-primary lbtn-sm" onClick={enter}>
              {authed ? 'Mon espace' : 'Accéder à l’application'}
              <ArrowRight size={15} />
            </button>
          </div>
        </div>
      </header>

      {/* ----------------------------------------------------------- héros */}
      <section className="hero">
        <div className="hero-grid-bg" />
        <div className="hero-inner">
          <div className="hero-copy">
            <span className="pill pill-dark reveal">
              <Sparkles size={14} /> Document AI · Contrôle des achats
            </span>
            <h1 className="hero-title reveal">
              Concordance
              <span>Commandé, livré, facturé&nbsp;: enfin d’accord.</span>
            </h1>
            <p className="hero-lead reveal">
              Concordance lit vos bons de commande, bons de livraison et factures, vérifie leurs
              calculs et les rapproche ligne par ligne, puis vous montre précisément
              <b> ce qui ne concorde pas</b>.
            </p>
            <div className="hero-ctas reveal">
              <button className="lbtn lbtn-primary" onClick={enter}>
                {authed ? 'Ouvrir mon espace' : 'Commencer une analyse'}
                <ArrowRight size={17} />
              </button>
              <button className="lbtn lbtn-glass" onClick={() => goto('problematique')}>
                Découvrir le projet
                <ArrowDown size={17} />
              </button>
            </div>
          </div>
          <div className="reveal reveal-delay">
            <HeroVisual />
          </div>
        </div>

        <div className="facts">
          {FACTS.map((f) => (
            <div key={f.label} className="fact reveal">
              <b>{f.value}</b>
              <span>{f.label}</span>
              <small>{f.sub}</small>
            </div>
          ))}
        </div>
      </section>

      {/* ---------------------------------------------------- problématique */}
      <section id="problematique" className="lsection">
        <div className="lsection-inner split">
          <div>
            <span className="section-kicker reveal">01 · Problématique</span>
            <h2 className="section-title reveal">
              Un contrôle indispensable, <em>mais fait à la main.</em>
            </h2>
            <p className="section-lead reveal">
              Avant de payer un fournisseur, il faut s’assurer que la facture correspond à ce qui a
              été commandé et réellement livré. Chez un client industriel tunisien, ce rapprochement
              était fait manuellement, document par document.
            </p>
            <blockquote className="question reveal">
              <span className="question-mark">?</span>
              Comment automatiser de façon fiable le rapprochement entre commandes, livraisons et
              factures, malgré des documents hétérogènes et souvent scannés, tout en laissant
              l’humain maître des cas ambigus&nbsp;?
            </blockquote>
          </div>
          <div className="reveal reveal-delay">
            <ProblemVisual />
          </div>
        </div>

        <div className="lsection-inner">
          <div className="pain-grid">
            {PAINS.map((p) => (
              <article key={p.title} className="pain reveal">
                <span className="pain-icon">
                  <p.icon size={20} />
                </span>
                <h3>{p.title}</h3>
                <p>{p.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* --------------------------------------------------------- solution */}
      <section id="solution" className="lsection lsection-tint">
        <div className="lsection-inner">
          <div className="section-head">
            <span className="section-kicker reveal">02 · Solution</span>
            <h2 className="section-title reveal">
              Trois gestes, <em>un seul dépôt de PDF.</em>
            </h2>
            <p className="section-lead reveal">
              L’opérateur dépose un PDF regroupant les pièces d’un même achat. Concordance fait le
              reste, et ne lui soumet que ce qui mérite son attention.
            </p>
          </div>
          <div className="pillars">
            {PILLARS.map((p) => (
              <article key={p.n} className="pillar reveal">
                <div className="pillar-top">
                  <span className="pillar-icon">
                    <p.icon size={22} />
                  </span>
                  <span className="pillar-n">{p.n}</span>
                </div>
                <h3>{p.title}</h3>
                <p>{p.text}</p>
              </article>
            ))}
          </div>
          <div className="callout reveal">
            <UserCheck size={22} />
            <div>
              <strong>L’humain garde le dernier mot.</strong>
              <span>
                Quand le système hésite, il le dit. L’opérateur tranche, corrige ou réaffecte, et
                toute la chaîne est rejouée sous ses décisions.
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------- fonctionnement */}
      <section id="fonctionnement" className="lsection lsection-dark">
        <div className="lsection-inner">
          <div className="section-head">
            <span className="section-kicker section-kicker-light reveal">03 · Fonctionnement</span>
            <h2 className="section-title reveal">
              Un pipeline en dix couches, <em>l’IA là où elle est utile.</em>
            </h2>
            <p className="section-lead reveal">
              Seules l’identification et l’extraction font appel au modèle. Tout ce qui suit est
              déterministe : mêmes documents, mêmes décisions, même verdict.
            </p>
          </div>
          <ol className="pipeline">
            {PIPELINE.map((s, i) => (
              <li key={s.title} className="pipe-step reveal" style={{ transitionDelay: `${i * 70}ms` }}>
                <div className="pipe-top">
                  <span className={`pipe-icon ${s.ai ? 'pipe-icon-ai' : ''}`}>
                    <s.icon size={20} />
                  </span>
                  <span className="pipe-layers">{s.layers}</span>
                </div>
                <h3>{s.title}</h3>
                <p>{s.text}</p>
                <span className={`pipe-tag ${s.ai ? 'pipe-tag-ai' : ''}`}>
                  {s.ai ? (
                    <>
                      <Cpu size={12} /> Vision-LLM
                    </>
                  ) : (
                    <>
                      <Database size={12} /> Déterministe
                    </>
                  )}
                </span>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* --------------------------------------------------------- résultats */}
      <section id="resultats" className="lsection">
        <div className="lsection-inner">
          <div className="section-head">
            <span className="section-kicker reveal">04 · Résultats</span>
            <h2 className="section-title reveal">
              Un verdict clair <em>pour chaque produit.</em>
            </h2>
            <p className="section-lead reveal">
              Chaque ligne du bon de commande reçoit un statut explicite, avec l’écart chiffré et les
              preuves de l’appariement.
            </p>
          </div>
          <div className="outcomes">
            {OUTCOMES.map((o) => (
              <div key={o.label} className={`outcome outcome-${o.tone} reveal`}>
                <span className={`badge badge-${o.tone}`}>
                  <span className="badge-dot" />
                  {o.label}
                </span>
                <p>{o.text}</p>
              </div>
            ))}
          </div>

          <div className="preview-wrap reveal">
            <AppPreview />
            <div className="preview-caption">
              <ListChecks size={16} /> Aperçu de l’écran de résultats (données d’exemple)
            </div>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------- fonctionnalités */}
      <section id="fonctionnalites" className="lsection lsection-tint">
        <div className="lsection-inner">
          <div className="section-head">
            <span className="section-kicker reveal">05 · Fonctionnalités</span>
            <h2 className="section-title reveal">
              Pensé pour la réalité <em>des documents fournisseurs.</em>
            </h2>
          </div>
          <div className="features">
            {FEATURES.map((f) => (
              <article key={f.title} className="feature reveal">
                <span className="feature-icon">
                  <f.icon size={20} />
                </span>
                <h3>{f.title}</h3>
                <p>{f.text}</p>
              </article>
            ))}
          </div>

          <div className="principles">
            {PRINCIPLES.map((p) => (
              <div key={p.title} className="principle reveal">
                <p.icon size={18} />
                <div>
                  <strong>{p.title}</strong>
                  <span>{p.text}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="stack-row reveal">
            <span className="stack-label">Technologies</span>
            {STACK.map((t) => (
              <span key={t} className="stack-chip">
                {t}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* -------------------------------------------------------------- CTA */}
      <section className="lsection">
        <div className="lsection-inner">
          <div className="cta reveal">
            <div className="cta-glow" />
            <div>
              <h2>Prêt à contrôler votre premier dossier&nbsp;?</h2>
              <p>Déposez un PDF : le résultat est prêt en quelques minutes.</p>
            </div>
            <button className="lbtn lbtn-accent" onClick={enter}>
              {authed ? 'Ouvrir mon espace' : 'Se connecter'}
              <ArrowRight size={17} />
            </button>
          </div>
        </div>
      </section>

      <footer className="lfoot">
        <div className="lfoot-inner">
          <Logo size={30} />
          <span>Rapprochement automatique des bons de commande, bons de livraison et factures.</span>
          <span className="lfoot-right">Projet d’ingénierie · v1.0</span>
        </div>
      </footer>
    </div>
  );
}
