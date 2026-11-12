import type { Metadata } from "next";
import Providers from "@/components/Providers";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/outfit/500.css";
import "./globals.css";
import "./design-system.css";
import "./reference-theme.css";

export const metadata: Metadata = {
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    title: "SafariOS",
    statusBarStyle: "black-translucent",
  },
  icons: { apple: "/icons/icon-192.png", icon: "/icons/icon-192.png" },
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
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{document.documentElement.dataset.theme=localStorage.getItem('theme')==='light'?'light':'dark'}catch(e){}",
          }}
        />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
