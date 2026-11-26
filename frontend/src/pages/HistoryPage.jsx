import { useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, FileStack, Plus } from 'lucide-react';

import { listAnalyses } from '../api/client.js';
import { useAsync } from '../lib/useAsync.js';
import { analysisStatus } from '../lib/status.js';
import { fmtDateTime } from '../lib/format.js';

import { PageHeader, Card } from '../components/ui/Card.jsx';
import Button from '../components/ui/Button.jsx';
import { AnalysisStatusBadge, DocSet } from '../components/ui/Badge.jsx';
import { ConfidenceMeter, FilterChips, SearchInput } from '../components/ui/Widgets.jsx';
import { EmptyState, ErrorState, LoadingBlock } from '../components/ui/Feedback.jsx';

const PAGE_SIZE = 15;

const FILTERS = [
  { key: 'all', label: 'Toutes' },
  { key: 'review', label: 'À réviser', tone: 'warn' },
  { key: 'gaps', label: 'Avec écarts', tone: 'err' },
  { key: 'ok', label: 'Conformes', tone: 'ok' },
  { key: 'scope', label: 'Hors périmètre' },
];

const SORTS = {
  date: (a) => new Date(a.date).getTime(),
  fichier: (a) => (a.fichier || '').toLowerCase(),
  confiance: (a) => a.confiance ?? -1,
  ecarts: (a) => a.totaux?.ecarts ?? -1,
};

function SortHeader({ label, k, sort, setSort, align }) {
  const active = sort.key === k;
  return (
    <th className={`th-sort ${align === 'right' ? 'text-right' : ''}`}>
      <button type="button" onClick={() => setSort({ key: k, dir: active && sort.dir === 'desc' ? 'asc' : 'desc' })}>
        {label}
        {active && (sort.dir === 'desc' ? <ArrowDown size={13} /> : <ArrowUp size={13} />)}
      </button>
    </th>
  );
}

export default function HistoryPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { data, error, loading, reload } = useAsync(() => listAnalyses(), []);

  const filter = params.get('filtre') || 'all';
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState({ key: 'date', dir: 'desc' });
  const [page, setPage] = useState(1);

  const counts = useMemo(() => {
    const c = { all: 0, review: 0, gaps: 0, ok: 0, scope: 0 };
    for (const a of data || []) {
      c.all += 1;
      const k = analysisStatus(a).key;
      if (k in c) c[k] += 1;
    }
    return c;
  }, [data]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const out = (data || []).filter((a) => {
      if (filter !== 'all' && analysisStatus(a).key !== filter) return false;
      if (q && !(a.fichier || '').toLowerCase().includes(q) && !String(a.id).includes(q)) return false;
      return true;
    });
    const key = SORTS[sort.key];
    out.sort((x, y) => {
      const a = key(x);
      const b = key(y);
      const r = a < b ? -1 : a > b ? 1 : 0;
      return sort.dir === 'desc' ? -r : r;
    });
    return out;
  }, [data, filter, query, sort]);

  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const current = Math.min(page, pages);
  const visible = rows.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);

  return (
    <div className="page">
      <PageHeader
        eyebrow="Analyses"
        title="Historique des analyses"
        subtitle="Toutes les analyses enregistrées, de la plus récente à la plus ancienne."
        actions={
          <Button variant="primary" icon={Plus} onClick={() => navigate('/app/analyses/nouvelle')}>
            Nouvelle analyse
          </Button>
        }
      />

      <Card padded={false}>
        <div className="toolbar">
          <FilterChips
            value={filter}
            onChange={(k) => {
              setParams(k === 'all' ? {} : { filtre: k });
              setPage(1);
            }}
            options={FILTERS.map((f) => ({ ...f, count: counts[f.key] }))}
          />
          <SearchInput
            value={query}
            onChange={(v) => {
              setQuery(v);
              setPage(1);
            }}
            placeholder="Nom de fichier ou n° d'analyse"
          />
        </div>

        {error ? (
          <div className="card-body"><ErrorState error={error} onRetry={reload} /></div>
        ) : loading && !data ? (
          <LoadingBlock />
        ) : !rows.length ? (
          <EmptyState
            icon={FileStack}
            title="Aucune analyse"
            text={data?.length ? 'Aucune analyse ne correspond à ces critères.' : 'Aucune analyse enregistrée pour le moment.'}
          />
        ) : (
          <>
            <table className="table table-hover">
              <thead>
                <tr>
                  <th className="col-id">N°</th>
                  <SortHeader label="Fichier" k="fichier" sort={sort} setSort={setSort} />
                  <th>Pièces</th>
                  <SortHeader label="Date" k="date" sort={sort} setSort={setSort} />
                  <th className="text-right">Pages</th>
                  <SortHeader label="Produits" k="ecarts" sort={sort} setSort={setSort} align="right" />
                  <SortHeader label="Confiance" k="confiance" sort={sort} setSort={setSort} />
                  <th>Statut</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((a) => (
                  <tr key={a.id} onClick={() => navigate(`/app/analyses/${a.id}`)}>
                    <td className="mono text-muted">#{a.id}</td>
                    <td className="cell-strong cell-ellipsis" title={a.fichier}>{a.fichier}</td>
                    <td><DocSet types={a.documents} /></td>
                    <td className="text-muted nowrap">{fmtDateTime(a.date)}</td>
                    <td className="text-right mono">{a.pages ?? '—'}</td>
                    <td className="text-right mono">
                      {a.totaux ? (
                        <>
                          <span className="text-ok">{a.totaux.conformes}</span>
                          <span className="text-muted"> / {a.totaux.produits}</span>
                        </>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td><ConfidenceMeter value={a.confiance} compact /></td>
                    <td><AnalysisStatusBadge analysis={a} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="pagination">
              <span className="text-muted small">
                {rows.length} analyse{rows.length > 1 ? 's' : ''} · page {current} / {pages}
              </span>
              <div className="pagination-btns">
                <Button size="sm" icon={ChevronLeft} disabled={current <= 1} onClick={() => setPage(current - 1)} aria-label="Page précédente" />
                <Button size="sm" icon={ChevronRight} disabled={current >= pages} onClick={() => setPage(current + 1)} aria-label="Page suivante" />
              </div>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
