import * as React from 'react'
import { cn } from '@/lib/utils/cn'

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', ...props }, ref) => {
    return (
      <button
        className={cn(
          // Base — tight tracking, no heavy shadows
          'inline-flex items-center justify-center rounded-button font-medium tracking-tight transition-all duration-150',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus)] focus-visible:ring-offset-1',
          'focus-visible:ring-offset-[var(--bg)]',
          'disabled:pointer-events-none disabled:opacity-40',

          // ── Variants ────────────────────────────────────────────────────────
          {
            // Primary: solid teal CTA — used sparingly
            'bg-primary text-white hover:bg-primary-dark active:scale-[0.97]':
              variant === 'primary',

            // Secondary: muted surface, hairline border
            'bg-surface-elevated text-text-secondary border border-hairline hover:text-text-primary hover:bg-surface-elevated':
              variant === 'secondary',

            // Outline: teal hairline border; no fill
            'border border-primary/40 text-primary hover:bg-primary/[8%] hover:border-primary/70':
              variant === 'outline',

            // Ghost: text only — lowest visual weight
            'text-text-secondary hover:text-text-primary hover:bg-surface-elevated':
              variant === 'ghost',
          },

          // ── Sizes ────────────────────────────────────────────────────────────
          {
            'h-8 px-3 text-xs gap-1.5': size === 'sm',
            'h-10 px-5 text-sm gap-2':  size === 'md',
            'h-12 px-7 text-base gap-2': size === 'lg',
          },

          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = 'Button'

export { Button }
