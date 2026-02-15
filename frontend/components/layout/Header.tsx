'use client'

import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Menu, X } from 'lucide-react'
import { useState } from 'react'

export function Header() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

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

        {/* Desktop CTA Button */}
        <div className="hidden md:block ml-6">
          <Link href="/analyze">
            <Button size="sm">Analyze Stock</Button>
          </Link>
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
            <Link href="/analyze" onClick={() => setMobileMenuOpen(false)}>
              <Button size="sm" className="w-full">Analyze Stock</Button>
            </Link>
          </nav>
        </div>
      )}
    </header>
  )
}
