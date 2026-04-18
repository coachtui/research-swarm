import Link from 'next/link'

/**
 * Compact inline disclaimer for pages that display verdicts, signals, or price targets.
 * Place at the bottom of leaderboard, report, and portfolio pages.
 */
export function InlineDisclaimer() {
  return (
    <p className="text-xs text-muted-foreground text-center py-2">
      For informational purposes only. Not financial advice. Past signals do not
      guarantee future performance. Always conduct your own research.{' '}
      <Link href="/disclaimer" className="underline hover:text-foreground transition-colors">
        Full disclaimer
      </Link>
    </p>
  )
}
