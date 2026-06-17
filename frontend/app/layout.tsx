import type { Metadata } from "next";
import { IBM_Plex_Sans, JetBrains_Mono } from "next/font/google";

import "./globals.css";

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
});

const ibmPlexSans = IBM_Plex_Sans({
  variable: "--font-ibm-plex",
  weight: ["400", "500", "600"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "TechPulse",
  description:
    "Feed de inteligência técnica filtrado por IA. Sinal limpo para engenheiros de software.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="pt-BR"
      className={`${jetbrainsMono.variable} ${ibmPlexSans.variable} h-full`}
      suppressHydrationWarning
    >
      <body className="min-h-full bg-slate-dark text-foreground antialiased">
        {children}
      </body>
    </html>
  );
}
