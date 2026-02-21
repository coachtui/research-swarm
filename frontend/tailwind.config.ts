import type { Config } from 'tailwindcss'

// Colors reference CSS custom properties defined in globals.css.
// Using the `rgb(var(--*-rgb) / <alpha-value>)` pattern so that Tailwind's
// opacity modifier syntax (e.g. `bg-background/80`, `text-primary/20`) works
// correctly alongside the theme token layer.

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // ── Brand accent ───────────────────────────────────────────────────
        // Use sparingly: only for interactive/active/CTA/focus states.
        primary: {
          DEFAULT: 'rgb(var(--accent-rgb) / <alpha-value>)',
          dark:    'rgb(var(--accent-dark-rgb) / <alpha-value>)',
          light:   'rgb(var(--accent-light-rgb) / <alpha-value>)',
        },

        // ── Theme-aware surfaces ────────────────────────────────────────────
        background: 'rgb(var(--bg-rgb) / <alpha-value>)',
        surface: {
          DEFAULT:  'rgb(var(--surface-1-rgb) / <alpha-value>)',
          elevated: 'rgb(var(--surface-2-rgb) / <alpha-value>)',
        },

        // ── Theme-aware text ────────────────────────────────────────────────
        text: {
          primary:   'rgb(var(--text-rgb) / <alpha-value>)',
          secondary: 'rgb(var(--text-muted-rgb) / <alpha-value>)',
          tertiary:  'rgb(var(--text-subtle-rgb) / <alpha-value>)',
        },

        // ── Semantic (fixed — same in both themes) ──────────────────────────
        success: '#10B981',
        warning: '#F59E0B',
        error:   '#EF4444',
        info:    '#3B82F6',

        // ── Chart ───────────────────────────────────────────────────────────
        chart: {
          strong:   '#10B981',
          moderate: '#F59E0B',
          weak:     '#EF4444',
        },
      },

      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },

      fontSize: {
        xs:   '0.75rem',   // 12px
        sm:   '0.875rem',  // 14px
        base: '1rem',      // 16px
        lg:   '1.125rem',  // 18px
        xl:   '1.25rem',   // 20px
        '2xl': '1.5rem',   // 24px
        '3xl': '1.875rem', // 30px
        '4xl': '2.25rem',  // 36px
      },

      borderRadius: {
        // Tighter radii for the Framework Guide / institutional look
        card:   '8px',
        button: '6px',
      },

      boxShadow: {
        // Reference CSS variable so shadows respect theme
        theme:    'var(--shadow)',
        'theme-sm': 'var(--shadow-sm)',
      },
    },
  },
  plugins: [],
}

export default config
