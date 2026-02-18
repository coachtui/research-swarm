'use client'

import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Menu, X } from 'lucide-react'
import { useState } from 'react'
import { UserButton, useUser } from '@clerk/nextjs'

export function Header() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const { isSignedIn, user } = useUser()

  return (
    <header className="sticky top-0 z-50 w-full border-b border-surface-elevated bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex h-16 items-center px-4">
        {/* Logo */}
        <Link href="/" className="flex items-center space-x-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
            <span className="text-lg font-bold text-white">D</span>
          </div>
          <span className="text-xl font-bold text-text-primary">DVRG</span>
        </Link>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Desktop Navigation */}
        <nav className="hidden md:flex items-center space-x-6">
          <Link
            href="/dashboard"
            className="text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            Dashboard
          </Link>
          <Link
            href="/#how-it-works"
            className="text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            How It Works
          </Link>
          <Link
            href="/#pricing"
            className="text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            Pricing
          </Link>
          <Link
            href="/#faq"
            className="text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            FAQ
          </Link>
        </nav>

        {/* Desktop Auth */}
        <div className="hidden md:flex items-center gap-3 ml-6">
          {isSignedIn ? (
            <>
              <Link href="/analyze">
                <Button size="sm">Analyze Stock</Button>
              </Link>
              <UserButton
                afterSignOutUrl="/"
                appearance={{
                  elements: {
                    avatarBox: "w-8 h-8",
                  },
                }}
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

        {/* Mobile Menu Button */}
        <button
          className="md:hidden ml-4 p-2 text-text-secondary hover:text-text-primary"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          aria-label="Toggle menu"
        >
          {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Mobile Navigation */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-surface-elevated bg-surface">
          <nav className="container mx-auto px-4 py-4 flex flex-col space-y-4">
            <Link
              href="/dashboard"
              className="text-sm text-text-secondary hover:text-text-primary transition-colors py-2"
              onClick={() => setMobileMenuOpen(false)}
            >
              Dashboard
            </Link>
            <Link
              href="/#how-it-works"
              className="text-sm text-text-secondary hover:text-text-primary transition-colors py-2"
              onClick={() => setMobileMenuOpen(false)}
            >
              How It Works
            </Link>
            <Link
              href="/#pricing"
              className="text-sm text-text-secondary hover:text-text-primary transition-colors py-2"
              onClick={() => setMobileMenuOpen(false)}
            >
              Pricing
            </Link>
            <Link
              href="/#faq"
              className="text-sm text-text-secondary hover:text-text-primary transition-colors py-2"
              onClick={() => setMobileMenuOpen(false)}
            >
              FAQ
            </Link>
            <div className="flex flex-col gap-2 pt-2 border-t border-surface-elevated">
              {isSignedIn ? (
                <>
                  <Link href="/analyze" onClick={() => setMobileMenuOpen(false)}>
                    <Button size="sm" className="w-full">Analyze Stock</Button>
                  </Link>
                  <div className="flex items-center justify-between py-2 px-2">
                    <span className="text-sm text-text-secondary">
                      {user?.primaryEmailAddress?.emailAddress}
                    </span>
                    <UserButton
                      afterSignOutUrl="/"
                      appearance={{
                        elements: {
                          avatarBox: "w-8 h-8",
                        },
                      }}
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
