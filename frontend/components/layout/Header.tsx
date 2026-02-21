'use client'

import Link from 'next/link'
import Image from 'next/image'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/ui/theme-toggle'
import { Menu, X } from 'lucide-react'
import { useState } from 'react'
import { UserButton, useUser } from '@clerk/nextjs'

const NAV_LINKS = [
  { href: '/dashboard',     label: 'Dashboard'    },
  { href: '/#how-it-works', label: 'How It Works' },
  { href: '/#pricing',      label: 'Pricing'      },
  { href: '/#faq',          label: 'FAQ'           },
]

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
      <div className="container mx-auto flex h-14 items-center px-4">

        {/* Logo */}
        <Link href="/" className="flex items-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] rounded">
          <Image src="/dvrg-logo.png" alt="DVRG" width={110} height={36} className="h-9 w-auto" priority />
        </Link>

        <div className="flex-1" />

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-1 mr-4">
          {NAV_LINKS.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className="px-3 py-1.5 rounded-md text-sm transition-colors duration-150
                         text-text-secondary hover:text-text-primary hover:bg-surface
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
            >
              {label}
            </Link>
          ))}
        </nav>

        {/* Theme toggle — desktop */}
        <div className="hidden md:flex items-center">
          <ThemeToggle />
        </div>

        {/* Desktop auth */}
        <div className="hidden md:flex items-center gap-2 ml-4">
          {isSignedIn ? (
            <>
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
                <Button size="sm">Get Started</Button>
              </Link>
            </>
          )}
        </div>

        {/* Mobile menu toggle */}
        <button
          className="md:hidden ml-3 p-2 rounded-md text-text-secondary hover:text-text-primary
                     hover:bg-surface transition-colors duration-150
                     focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-label="Toggle menu"
        >
          {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Mobile navigation drawer */}
      {mobileMenuOpen && (
        <div
          className="md:hidden"
          style={{ borderTop: '1px solid var(--border)', background: 'var(--surface-1)' }}
        >
          <nav className="container mx-auto px-4 py-4 flex flex-col gap-1">
            {NAV_LINKS.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className="text-sm text-text-secondary hover:text-text-primary hover:bg-surface
                           transition-colors duration-150 py-2.5 px-3 rounded-md"
                onClick={() => setMobileMenuOpen(false)}
              >
                {label}
              </Link>
            ))}

            {/* Theme toggle — mobile */}
            <div className="pt-3 pb-1">
              <ThemeToggle />
            </div>

            {/* Auth — mobile */}
            <div
              className="flex flex-col gap-2 pt-3"
              style={{ borderTop: '1px solid var(--border)' }}
            >
              {isSignedIn ? (
                <>
                  <Link href="/analyze" onClick={() => setMobileMenuOpen(false)}>
                    <Button size="sm" className="w-full">Analyze Stock</Button>
                  </Link>
                  <div className="flex items-center justify-between py-2 px-2">
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
                    <Button size="sm" className="w-full">Get Started</Button>
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
