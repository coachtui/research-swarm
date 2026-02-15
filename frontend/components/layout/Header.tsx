import Link from 'next/link'
import { Button } from '@/components/ui/button'

export function Header() {
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

        {/* Navigation */}
        <nav className="flex items-center space-x-6">
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

        {/* CTA Button */}
        <div className="ml-6">
          <Link href="/analyze">
            <Button size="sm">Analyze Stock</Button>
          </Link>
        </div>
      </div>
    </header>
  )
}
