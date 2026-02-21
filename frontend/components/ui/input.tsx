import * as React from 'react'
import { cn } from '@/lib/utils/cn'

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {}

// Framework Guide input: elevated surface, hairline border at rest,
// teal focus ring on interaction.
const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          'flex h-10 w-full rounded-button px-4 py-2',
          'text-sm text-text-primary bg-surface-elevated',
          'border border-hairline',
          'placeholder:text-text-tertiary',
          'transition-colors duration-150',
          'focus-visible:outline-none',
          'focus-visible:ring-2 focus-visible:ring-[var(--focus)]',
          'focus-visible:ring-offset-1 focus-visible:ring-offset-[var(--bg)]',
          'focus-visible:border-primary/40',
          'disabled:cursor-not-allowed disabled:opacity-40',
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Input.displayName = 'Input'

export { Input }
