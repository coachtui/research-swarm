'use client'

import { useState, useEffect, useCallback } from 'react'
import { Moon, Sun } from 'lucide-react'

type ThemeValue = 'dark' | 'light'

function applyTheme(t: ThemeValue) {
  document.documentElement.setAttribute('data-theme', t)
}

/**
 * Single circular icon button that toggles between dark ↔ light.
 * - Dark mode  → shows Sun  (click to go light)
 * - Light mode → shows Moon (click to go dark)
 * Persists to localStorage["theme"]. "system" mode is retired.
 */
export function ThemeButton() {
  const [theme, setTheme] = useState<ThemeValue>('dark')
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    const stored = localStorage.getItem('theme')
    // Migrate legacy "system" → "dark"
    const resolved: ThemeValue = stored === 'light' ? 'light' : 'dark'
    setTheme(resolved)
    applyTheme(resolved)
  }, [])

  const toggle = useCallback(() => {
    const next: ThemeValue = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    localStorage.setItem('theme', next)
    applyTheme(next)
  }, [theme])

  // Stable placeholder — no layout shift before hydration
  if (!mounted) {
    return (
      <div
        aria-hidden
        className="w-8 h-8 rounded-full shrink-0"
        style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
      />
    )
  }

  return (
    <button
      onClick={toggle}
      aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      className={[
        'w-8 h-8 rounded-full shrink-0',
        'flex items-center justify-center',
        'transition-all duration-150',
        'hover:brightness-110 active:scale-95',
        'focus-visible:outline-none focus-visible:ring-2',
        'focus-visible:ring-[var(--focus)] focus-visible:ring-offset-1',
        'focus-visible:ring-offset-[var(--bg)]',
      ].join(' ')}
      style={{
        background: 'var(--surface-2)',
        border: '1px solid var(--border)',
        color: 'var(--text-muted)',
      }}
    >
      {theme === 'dark'
        ? <Sun  size={14} strokeWidth={1.6} />
        : <Moon size={14} strokeWidth={1.6} />
      }
    </button>
  )
}

// Backward-compat alias so existing imports still resolve
export { ThemeButton as ThemeToggle }
