import type { Metadata } from 'next';
import './globals.css';
import './design-system.css';

export const metadata: Metadata = { title: 'SafariOS · Lodge operations', description: 'SafariOS — the operating system for exceptional lodge hospitality' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en" suppressHydrationWarning><body>{children}</body></html>;
}
