import type { Metadata } from "next";
import Providers from "@/components/Providers";
import "@fontsource/archivo/400.css";
import "@fontsource/archivo/500.css";
import "@fontsource/archivo/600.css";
import "@fontsource/archivo-narrow/600.css";
import "./globals.css";
import "./design-system.css";

export const metadata: Metadata = {
  title: "SafariOS · Lodge operations",
  description:
    "SafariOS — the operating system for exceptional lodge hospitality",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" data-theme="light" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{document.documentElement.dataset.theme=localStorage.getItem('theme')==='dark'?'dark':'light'}catch(e){}",
          }}
        />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
