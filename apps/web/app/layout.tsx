import type { Metadata } from "next";
import Providers from "@/components/Providers";
import { GeistSans } from "geist/font/sans";
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
    <html
      lang="en"
      data-theme="dark"
      className={GeistSans.className}
      suppressHydrationWarning
    >
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
