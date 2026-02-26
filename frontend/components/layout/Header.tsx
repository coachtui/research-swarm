'use client'

import Link from 'next/link'
import Image from 'next/image'
import { Button } from '@/components/ui/button'
import { ThemeButton } from '@/components/ui/theme-toggle'
import { Menu, X, TrendingUp } from 'lucide-react'
import { useState } from 'react'
import { UserButton, useUser } from '@clerk/nextjs'
import { useEntitlements } from '@/lib/hooks/useEntitlements'

const PUBLIC_NAV_LINKS = [
  { href: '/#how-it-works', label: 'How It Works' },
  { href: '/#pricing',      label: 'Pricing'      },
  { href: '/#faq',          label: 'FAQ'           },
]

const AUTH_NAV_LINKS = [
  { href: '/dashboard',     label: 'Dashboard'    },
  ...PUBLIC_NAV_LINKS,
]

/**
 * Upgrade CTA chip shown in the header for:
 *   - Free users (always, to drive conversion)
 *   - Paid users who have hit ≥80% of their monthly quota (soft nudge)
 */
function UpgradeChip() {
  const { data: ents } = useEntitlements()
  if (!ents) return null

  const isFreeTier = ents.usage.is_free_tier
  const atWarning = ents.usage.at_warning_threshold
  const creditsLeft = ents.usage.report_credits_remaining

  // Show for free tier or paid users at/near limit
  const showUpgrade = isFreeTier || atWarning
  if (!showUpgrade) return null

  const label = isFreeTier
    ? creditsLeft === 0
      ? 'Upgrade'
      : `${creditsLeft} free report${creditsLeft !== 1 ? 's' : ''} left · Upgrade`
    : 'Upgrade'

  return (
    <Link
      href="/#pricing"
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold
                 bg-primary/10 text-primary border border-primary/20
                 hover:bg-primary/20 transition-colors duration-150"
      aria-label="Upgrade your plan"
    >
      <TrendingUp className="h-3.5 w-3.5" />
      {label}
    </Link>
  )
}

export function Header() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const { isSignedIn, user } = useUser()

  return (
    <header
      className="sticky top-0 z-50 w-full backdrop-blur supports-[backdrop-filter]:bg-background/60"
      style={{
        background: 'rgb(var(--bg-rgb) / 0.95)',
        borderBottom: '1px solid var(--border)',
      }}
    >
      <div className="container mx-auto flex h-14 items-center gap-6 px-4">

        {/* Logo */}
        <Link
          href="/"
          className="flex items-center shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] rounded"
        >
          <Image src="/dvrg-logo.png" alt="DVRG" width={100} height={34} className="h-8 w-auto" priority />
        </Link>

        <div className="flex-1" />

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-0.5">
          {(isSignedIn ? AUTH_NAV_LINKS : PUBLIC_NAV_LINKS).map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className="px-3 py-1.5 rounded-md text-sm text-text-secondary hover:text-text-primary
                         hover:bg-surface-elevated transition-colors duration-150
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
            >
              {label}
            </Link>
          ))}
        </nav>

        {/* Desktop right: theme + auth */}
        <div className="hidden md:flex items-center gap-2">
          <ThemeButton />

          {isSignedIn ? (
            <>
              {/* Upgrade chip — visible for free users + paid users near limit */}
              <UpgradeChip />
              <Link href="/analyze">
                <Button size="sm">Analyze Stock</Button>
              </Link>
              <UserButton
                afterSignOutUrl="/"
                appearance={{ elements: { avatarBox: 'w-8 h-8' } }}
              />
            </>
          ) : (
            <>
              <Link href="/sign-in">
                <Button variant="ghost" size="sm">Sign In</Button>
              </Link>
              <Link href="/sign-up">
                <Button size="sm">Get Started Free</Button>
              </Link>
            </>
          )}
        </div>

        {/* Mobile: theme + hamburger */}
        <div className="md:hidden flex items-center gap-2 ml-2">
          <ThemeButton />
          <button
            className="p-1.5 rounded-md text-text-secondary hover:text-text-primary
                       hover:bg-surface-elevated transition-colors duration-150
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {/* Mobile navigation drawer */}
      {mobileMenuOpen && (
        <div style={{ borderTop: '1px solid var(--border)', background: 'var(--surface-1)' }}>
          <nav className="container mx-auto px-4 py-3 flex flex-col gap-0.5">
            {(isSignedIn ? AUTH_NAV_LINKS : PUBLIC_NAV_LINKS).map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className="text-sm text-text-secondary hover:text-text-primary
                           hover:bg-surface-elevated px-3 py-2.5 rounded-md
                           transition-colors duration-150"
                onClick={() => setMobileMenuOpen(false)}
              >
                {label}
              </Link>
            ))}

            {/* Mobile auth */}
            <div className="flex flex-col gap-2 pt-3 mt-1" style={{ borderTop: '1px solid var(--border)' }}>
              {isSignedIn ? (
                <>
                  {/* Upgrade chip mobile */}
                  <UpgradeChip />
                  <Link href="/analyze" onClick={() => setMobileMenuOpen(false)}>
                    <Button size="sm" className="w-full">Analyze Stock</Button>
                  </Link>
                  <div className="flex items-center justify-between py-1.5 px-1">
                    <span className="text-sm text-text-secondary truncate">
                      {user?.primaryEmailAddress?.emailAddress}
                    </span>
                    <UserButton
                      afterSignOutUrl="/"
                      appearance={{ elements: { avatarBox: 'w-8 h-8' } }}
                    />
                  </div>
                </>
              ) : (
                <>
                  <Link href="/sign-in" onClick={() => setMobileMenuOpen(false)}>
                    <Button variant="ghost" size="sm" className="w-full">Sign In</Button>
                  </Link>
                  <Link href="/sign-up" onClick={() => setMobileMenuOpen(false)}>
                    <Button size="sm" className="w-full">Get Started Free</Button>
                  </Link>
                </>
              )}
            </div>
          </nav>
        </div>
      )}
    </header>
  )
}
