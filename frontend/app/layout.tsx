import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { QueryProvider } from '@/lib/providers/query-provider'
import { Header } from '@/components/layout/Header'
import { Footer } from '@/components/layout/Footer'

const inter = Inter({ subsets: ['latin'] })

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
    <html lang="en" className="dark">
      <body className={`${inter.className} flex min-h-screen flex-col`}>
        <QueryProvider>
          <Header />
          <main className="flex-1">{children}</main>
          <Footer />
        </QueryProvider>
      </body>
    </html>
  )
}
