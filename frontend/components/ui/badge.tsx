import * as React from 'react'
import { cn } from '@/lib/utils/cn'

// Framework Guide chip/pill:
//   idle    — dark pill + very faint border + muted text
//   active  — teal border + brighter teal text (for default variant)
//   semantic — coloured text + matching faint border, no bright fill

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'secondary'
}

function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <div
      className={cn(
        // Base pill
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium leading-none',
        'transition-colors duration-150',
        'focus:outline-none focus:ring-2 focus:ring-[var(--focus)] focus:ring-offset-1',

        // Variants — minimal fill; border + text carry the signal
        {
          // Teal / accent — active or "info" chip
          'bg-primary/[7%] text-primary border border-primary/[18%]':
            variant === 'default',

          // Semantic
          'bg-success/[7%] text-success border border-success/[18%]':
            variant === 'success',

          'bg-warning/[7%] text-warning border border-warning/[18%]':
            variant === 'warning',

          'bg-error/[7%] text-error border border-error/[18%]':
            variant === 'error',

          // Neutral / secondary — dark pill, faint hairline
          'bg-surface-elevated text-text-secondary border border-hairline':
            variant === 'secondary',
        },

        className
      )}
      {...props}
    />
  )
}

export { Badge }
