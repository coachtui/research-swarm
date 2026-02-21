'use client'

import { useState, useEffect, useCallback } from 'react'
import { Monitor, Moon, Sun } from 'lucide-react'

export type ThemePreference = 'system' | 'dark' | 'light'

/** Resolves the stored preference to an actual data-theme value. */
function resolveTheme(pref: ThemePreference): 'dark' | 'light' {
  if (pref === 'system') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  return pref
}

/** Applies a theme preference to the document root. */
function applyTheme(pref: ThemePreference) {
  document.documentElement.setAttribute('data-theme', resolveTheme(pref))
}

const OPTIONS: { value: ThemePreference; icon: React.ReactNode; label: string }[] = [
  { value: 'system', icon: <Monitor size={13} strokeWidth={1.7} />, label: 'System' },
  { value: 'dark',   icon: <Moon    size={13} strokeWidth={1.7} />, label: 'Dark'   },
  { value: 'light',  icon: <Sun     size={13} strokeWidth={1.7} />, label: 'Light'  },
]

export function ThemeToggle() {
  const [theme, setTheme] = useState<ThemePreference>('system')
  const [mounted, setMounted] = useState(false)

  // Read stored preference on mount
  useEffect(() => {
    setMounted(true)
    const stored = (localStorage.getItem('theme') as ThemePreference | null) ?? 'system'
    setTheme(stored)
  }, [])

  // When in "system" mode, follow OS preference changes
  useEffect(() => {
    if (theme !== 'system') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => applyTheme('system')
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [theme])

  const handleChange = useCallback((next: ThemePreference) => {
    setTheme(next)
    localStorage.setItem('theme', next)
    applyTheme(next)
  }, [])

  // Avoid hydration mismatch: render a stable placeholder until mounted
  if (!mounted) {
    return (
      <div
        aria-hidden
        className="h-8 w-[106px] rounded-full"
        style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}
      />
    )
  }

  return (
    <div
      role="group"
      aria-label="Color theme"
      className="flex items-center rounded-full p-0.5 gap-px"
      style={{
        background: 'var(--surface-1)',
        border: '1px solid var(--border)',
      }}
    >
      {OPTIONS.map(({ value, icon, label }) => {
        const active = theme === value
        return (
          <button
            key={value}
            onClick={() => handleChange(value)}
            aria-label={`${label} theme`}
            title={`${label} theme`}
            className={[
              'flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-xs font-medium',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1',
              'transition-colors duration-150',
              active ? '' : 'hover:text-[var(--text)]',
            ].join(' ')}
            style={
              active
                ? {
                    color: 'var(--accent)',
                    background: 'var(--surface-2)',
                    border: '1px solid var(--accent-border)',
                    boxShadow: 'var(--shadow-sm)',
                  }
                : {
                    color: 'var(--text-muted)',
                    border: '1px solid transparent',
                  }
            }
          >
            {icon}
            <span className="hidden sm:inline">{label}</span>
          </button>
        )
      })}
    </div>
  )
}
