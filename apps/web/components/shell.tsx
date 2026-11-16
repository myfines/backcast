'use client';
import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';
import { BookOpenCheck, Bookmark, Compass, FilePlus2, Menu, Scale, ShieldCheck, X } from 'lucide-react';
import { Suspense, useEffect, useState, type ReactNode } from 'react';
import { allAuthors, api, type Health } from '@/lib/api';

type ShellData = { domains: string[]; followed: number; health?: Health };

function useShellData(pathname: string) {
  const [data, setData] = useState<ShellData>({ domains: [], followed: 0 });
  useEffect(() => {
    let live = true;
    Promise.all([allAuthors(), api.health().catch(() => undefined)])
      .then(([authors, health]) => {
        if (!live) return;
        const domains = [...new Set(authors.map((a) => a.domain))];
        setData({ domains, followed: authors.filter((a) => a.followed).length, health });
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
    // Refresh counts on navigation (follow state can change on any page).
  }, [pathname]);
  useEffect(() => {
    const onChange = () => {
      allAuthors()
        .then((authors) => setData((d) => ({ ...d, followed: authors.filter((a) => a.followed).length })))
        .catch(() => undefined);
    };
    window.addEventListener('backcast:follow', onChange);
    return () => window.removeEventListener('backcast:follow', onChange);
  }, []);
  return data;
}

function NavLinks({ data }: { data: ShellData }) {
  const pathname = usePathname();
  const params = useSearchParams();
  const followedView = pathname === '/' && params.get('followed') === '1';
  const domain = pathname === '/' ? params.get('domain') : null;
  const items: { href: string; label: string; icon: ReactNode; active: boolean; count?: number }[] = [
    { href: '/', label: '发现预测者', icon: <Compass size={17} aria-hidden />, active: pathname === '/' && !followedView && !domain },
    { href: '/?followed=1', label: '我的关注', icon: <Bookmark size={17} aria-hidden />, active: followedView, count: data.followed },
    { href: '/compare', label: '对比判断记录', icon: <Scale size={17} aria-hidden />, active: pathname.startsWith('/compare') },
    { href: '/import', label: '添加判断记录', icon: <FilePlus2 size={17} aria-hidden />, active: pathname.startsWith('/import') },
    { href: '/methodology', label: '评价方法', icon: <BookOpenCheck size={17} aria-hidden />, active: pathname.startsWith('/methodology') },
    { href: '/review', label: '人工复核', icon: <ShieldCheck size={17} aria-hidden />, active: pathname.startsWith('/review') },
  ];
  return (
    <>
      <nav className="nav" aria-label="主导航">
        {items.map((it) => (
          <Link key={it.href} href={it.href} aria-current={it.active ? 'page' : undefined}>
            {it.icon}
            {it.label}
            {it.count !== undefined && <span className="count">{it.count}</span>}
          </Link>
        ))}
      </nav>
      {data.domains.length > 0 && (
        <>
          <div className="side-label">按领域浏览</div>
          <nav className="side-domains" aria-label="领域">
            {data.domains.map((d) => (
              <Link key={d} href={`/?domain=${encodeURIComponent(d)}`} aria-current={domain === d ? 'page' : undefined}>
                <span className="dot" aria-hidden />
                {d}
              </Link>
            ))}
          </nav>
        </>
      )}
    </>
  );
}

function Brand() {
  return (
    <Link href="/" className="brand" aria-label="Backcast 合订本 首页">
      <span className="brand-word">backcast</span>
      <span className="brand-sub">合订本</span>
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const data = useShellData(pathname);
  useEffect(() => setOpen(false), [pathname]);
  const h = data.health;
  return (
    <div className="shell">
      <header className="topbar">
        <Brand />
        <button className="icon-btn" aria-label="切换菜单" aria-expanded={open} aria-controls="sidebar" onClick={() => setOpen((o) => !o)}>
          {open ? <X size={20} aria-hidden /> : <Menu size={20} aria-hidden />}
        </button>
      </header>
      <div className={'scrim' + (open ? ' open' : '')} onClick={() => setOpen(false)} aria-hidden />
      <aside id="sidebar" className={'sidebar' + (open ? ' open' : '')} aria-label="侧边栏">
        <Brand />
        <p className="brand-line">让时间介绍专家。</p>
        <Suspense fallback={null}>
          <NavLinks data={data} />
        </Suspense>
        <div className="side-foot">
          <strong>只看记录，不看声量</strong>
          不以粉丝数、语气或一次命中推断专业能力；样本不足时如实显示。
          <div className="service-line" title="来自 /api/health">
            <span className={'service-dot' + (h?.ai ? ' on' : '')} aria-hidden />
            {h ? (h.ai ? 'AI 抽取已启用' : 'AI 未配置 · 使用规则抽取') : '后端状态未知'}
          </div>
          <div className="service-line">
            <span className={'service-dot' + (h?.search ? ' on' : '')} aria-hidden />
            {h ? (h.search ? '外部检索已启用' : '外部检索未配置') : '—'}
          </div>
        </div>
      </aside>
      <main className="main" id="main">
        <div className="container">{children}</div>
        <footer className="container site-foot">
          <span>
            <span className="serif" style={{ fontWeight: 700, color: 'var(--ink)' }}>backcast</span> · 公开来源 · 保留原文 · 支持纠错
          </span>
          <Link href="/methodology">评价方法与来源</Link>
        </footer>
      </main>
    </div>
  );
}
