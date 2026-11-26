export default function Tabs({ tabs, value, onChange, variant = 'line' }) {
  return (
    <div className={`tabs tabs-${variant}`} role="tablist">
      {tabs.map((t) => {
        const Icon = t.icon;
        return (
          <button
            key={t.key}
            role="tab"
            type="button"
            aria-selected={value === t.key}
            disabled={t.disabled}
            className={`tab ${value === t.key ? 'tab-active' : ''}`}
            onClick={() => onChange(t.key)}
          >
            {Icon && <Icon size={15} />}
            <span>{t.label}</span>
            {t.count !== undefined && t.count !== null && (
              <span className={`tab-count ${t.countTone ? `tab-count-${t.countTone}` : ''}`}>{t.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
