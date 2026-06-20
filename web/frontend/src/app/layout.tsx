import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { SiteNav } from "@/components/site-nav";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ClinicalBridge — Bridging the Clinical Context Gap",
  description:
    "An LLM-powered multi-agent system that synthesizes EHR, RPM, and anamnesis data into a cited Clinical Context Brief.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <ThemeProvider>
          <SiteNav />
          <main className="flex-1">{children}</main>
          <footer className="border-t">
            <div className="mx-auto max-w-6xl px-4 py-8 text-sm text-muted-foreground">
              <p className="font-medium text-foreground">ClinicalBridge</p>
              <p className="mt-1 max-w-2xl">
                A capstone proof-of-concept (COP-3442 Prompt Engineering). All patient data is
                fully simulated. Not a medical device; for demonstration only.
              </p>
              <p className="mt-2">
                Team: Masa Bokhary · Mohamed Alkhozendar · Abdullah Salamoun · Mohamed Allabani
              </p>
            </div>
          </footer>
        </ThemeProvider>
      </body>
    </html>
  );
}
