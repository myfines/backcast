import type { Metadata, Viewport } from 'next';
import './globals.css';
import { AppShell } from '@/components/shell';

export const metadata: Metadata = {
  title: { default: 'Backcast 合订本 · 让时间介绍专家', template: '%s · Backcast 合订本' },
  description: '从历史判断与公开证据，发现值得持续关注的专业人士。',
};

export const viewport: Viewport = { themeColor: '#f5f2e9', width: 'device-width', initialScale: 1 };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
