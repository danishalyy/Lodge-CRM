import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = { title: 'LodgeOS CRM', description: 'AI lodge operating system' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en" suppressHydrationWarning><body>{children}</body></html>;
}
