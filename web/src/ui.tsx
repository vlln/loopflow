import type { HTMLAttributes, ReactNode } from 'react';
import { Activity, Box, Braces, Check, CircleStop, RefreshCw, X, Zap } from 'lucide-react';

import type { RunStatus } from './types';

const statusIcon = {
  running: Zap,
  waiting_input: Activity,
  cancelling: CircleStop,
  cancelled: CircleStop,
  done: Check,
  failed: X,
  stopped: CircleStop,
  stale: RefreshCw,
  unreadable: Braces,
} as const;

export function StatusBadge({ value }: { value: string }) {
  const Icon = statusIcon[value as RunStatus] ?? Activity;
  return <span className={`status status-${value}`}><Icon size={12} />{value}</span>;
}

export function IconButton({ label, children, onClick, active = false }: { label: string; children: ReactNode; onClick?: () => void; active?: boolean }) {
  return <button className={`icon-button ${active ? 'is-active' : ''}`} aria-label={label} title={label} onClick={onClick}>{children}</button>;
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="empty"><Box size={22} /><strong>{title}</strong><span>{detail}</span></div>;
}

export function ScrollArea({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={['scroll-area', className].filter(Boolean).join(' ')} {...props}>{children}</div>;
}

export function Metric({ label, value }: { label: string; value: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>;
}

export function Fact({ label, value }: { label: string; value: string }) {
  return <div className="fact"><span>{label}</span><strong>{value}</strong></div>;
}
