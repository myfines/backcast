'use client';
import { AlertCircle, Info, RotateCw, X } from 'lucide-react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { ApiError, Author } from '@/lib/api';
import { initials } from '@/lib/format';

export function Notice({ tone = 'neutral', title, children, icon = true }: { tone?: 'neutral' | 'info' | 'ok' | 'warn' | 'error'; title?: ReactNode; children?: ReactNode; icon?: boolean }) {
  return (
    <div className={`notice ${tone}`} role={tone === 'error' ? 'alert' : undefined}>
      {icon && (tone === 'error' ? <AlertCircle size={16} aria-hidden /> : <Info size={16} aria-hidden />)}
      <div>
        {title && <strong>{title}</strong>}
        {title && children ? <div>{children}</div> : children}
      </div>
    </div>
  );
}

export function ErrorState({ error, retry }: { error: ApiError | Error; retry?: () => void }) {
  return (
    <Notice tone="error" title="内容没有加载出来">
      <span>{error.message}</span>
      {retry && (
        <button className="btn small" style={{ marginLeft: 12 }} onClick={retry}>
          <RotateCw size={14} aria-hidden /> 重试
        </button>
      )}
    </Notice>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      {children}
    </div>
  );
}

export function Skeleton({ h = 18, w = '100%', style }: { h?: number; w?: number | string; style?: React.CSSProperties }) {
  return <div className="skeleton" style={{ height: h, width: w, ...style }} aria-hidden />;
}

export function CardSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid-cards" aria-busy="true" aria-label="正在读取">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="card pad" style={{ display: 'grid', gap: 12 }}>
          <div style={{ display: 'flex', gap: 12 }}>
            <Skeleton h={48} w={48} style={{ borderRadius: '50%' }} />
            <div style={{ flex: 1, display: 'grid', gap: 8 }}>
              <Skeleton h={20} w="60%" />
              <Skeleton h={14} w="40%" />
            </div>
          </div>
          <Skeleton h={14} />
          <Skeleton h={56} />
        </div>
      ))}
    </div>
  );
}

export function Avatar({ author, large = false }: { author: Pick<Author, 'name' | 'initials' | 'color'>; large?: boolean }) {
  return (
    <span className={'avatar' + (large ? ' large' : '')} style={{ background: author.color || undefined }} aria-hidden>
      {initials(author.name, author.initials)}
    </span>
  );
}

/** Accessible side drawer: labelled dialog, Esc to close, focus moved in and restored. */
export function Drawer({ label, onClose, closeLabel, children, actions }: { label: string; onClose: () => void; closeLabel: string; children: ReactNode; actions?: ReactNode }) {
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    panel.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = overflow;
      previous?.focus?.();
    };
  }, [onClose]);
  return (
    <>
      <div className="drawer-scrim" onClick={onClose} aria-hidden />
      <div className="drawer" role="dialog" aria-modal="true" aria-label={label} ref={panel} tabIndex={-1}>
        <div className="drawer-head">
          <span className="eyebrow">{label}</span>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            {actions}
            <button className="icon-btn" onClick={onClose} aria-label={closeLabel} title="关闭 (Esc)">
              <X size={18} aria-hidden />
            </button>
          </div>
        </div>
        <div className="drawer-body">{children}</div>
      </div>
    </>
  );
}

export function Tabs<T extends string>({ value, onChange, items, label }: { value: T; onChange: (v: T) => void; items: { value: T; label: string }[]; label: string }) {
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {items.map((it) => (
        <button key={it.value} role="tab" aria-selected={value === it.value} onClick={() => onChange(it.value)}>
          {it.label}
        </button>
      ))}
    </div>
  );
}

export function useToast(): [ReactNode, (msg: string) => void] {
  const [msg, setMsg] = useState<string>();
  useEffect(() => {
    if (!msg) return;
    const t = setTimeout(() => setMsg(undefined), 2600);
    return () => clearTimeout(t);
  }, [msg]);
  return [msg ? <div className="toast" role="status">{msg}</div> : null, setMsg];
}
