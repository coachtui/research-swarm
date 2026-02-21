import type { Metadata } from 'next'
import './globals.css'
import { ClerkProvider } from '@clerk/nextjs'
import { QueryProvider } from '@/lib/providers/query-provider'
import { TooltipProvider } from '@/components/ui/tooltip'
import { Header } from '@/components/layout/Header'
import { Footer } from '@/components/layout/Footer'
import { TokenProvider } from '@/components/auth/TokenProvider'
import { KnowledgeProvider } from '@/components/knowledge/KnowledgeProvider'

// Minified theme-init script — runs synchronously before first paint to avoid FOUC.
// Reads localStorage key "theme" (system|dark|light), resolves system to OS pref,
// and sets `data-theme` on <html> before React hydrates.
const THEME_INIT_SCRIPT = `(function(){try{var p=localStorage.getItem('theme')||'system';var t=p==='system'?(window.matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light'):p;document.documentElement.setAttribute('data-theme',t)}catch(e){}})();`

// Using system fonts as fallback due to Google Fonts timeout
const fontClass = 'font-sans'

export const viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
}

export const metadata: Metadata = {
  title: 'DVRG - AI Stock Analysis That Detects Divergences',
  description: 'Institutional-quality stock analysis powered by AI. Detect what Wall Street doesn\'t tell you in 4 minutes.',
  keywords: ['stock analysis', 'AI investing', 'moat score', 'divergence detection', 'investment research'],
  authors: [{ name: 'DVRG' }],
  creator: 'DVRG',
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: 'https://dvrg.ai',
    title: 'DVRG - AI Stock Analysis',
    description: 'Detect divergences before the market does. Institutional-quality research in 4 minutes.',
    siteName: 'DVRG',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'DVRG - AI Stock Analysis',
    description: 'Institutional-quality stock analysis powered by AI',
    creator: '@dvrg_ai',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <ClerkProvider dynamic>
      {/*
        suppressHydrationWarning: the inline script mutates data-theme before
        React hydrates, causing an expected mismatch that we can safely ignore.
      */}
      <html lang="en" suppressHydrationWarning>
        <head>
          {/* FOUC prevention — must run synchronously before CSS is applied */}
          <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
        </head>
        <body className={`${fontClass} flex min-h-screen flex-col`}>
          <QueryProvider>
            <TooltipProvider delayDuration={200}>
              <KnowledgeProvider>
                <TokenProvider />
                <Header />
                <main className="flex-1">{children}</main>
                <Footer />
              </KnowledgeProvider>
            </TooltipProvider>
          </QueryProvider>
        </body>
      </html>
    </ClerkProvider>
  )
}
