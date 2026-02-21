import { cn } from "@/lib/utils/cn"

function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('animate-pulse rounded-md', className)}
      style={{ background: 'var(--surface-2)', opacity: 0.6 }}
      {...props}
    />
  )
}

export { Skeleton }
