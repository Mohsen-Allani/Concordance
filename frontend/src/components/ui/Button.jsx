import { Loader2 } from 'lucide-react';

export default function Button({
  variant = 'secondary',
  size = 'md',
  icon: Icon,
  loading = false,
  children,
  className = '',
  ...props
}) {
  return (
    <button
      type="button"
      className={`btn btn-${variant} btn-${size} ${className}`}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading ? <Loader2 size={16} className="spin" /> : Icon && <Icon size={16} />}
      {children && <span>{children}</span>}
    </button>
  );
}
