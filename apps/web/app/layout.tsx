import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'Backcast 合订本 · 让时间介绍专家', description: '从历史判断与公开证据，发现值得持续关注的专业人士。' };
export default function RootLayout({ children }: Readonly<{children: React.ReactNode}>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
