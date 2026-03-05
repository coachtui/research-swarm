import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useAdminUsers, useUpdateUserTier } from '@/lib/hooks/useAdmin'
import { formatDateTime } from '@/lib/utils/formatting'
import { Shield, ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'

export function AdminUserTable() {
  const [page, setPage] = useState(0)
  const limit = 20
  const offset = page * limit

  const { data, isLoading } = useAdminUsers(limit, offset)
  const { mutate: updateTier, isPending: isUpdating } = useUpdateUserTier()

  const handleTierChange = (userId: string, newTier: string) => {
    if (confirm(`Change user tier to ${newTier}?`)) {
      updateTier({ userId, newTier })
    }
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Users</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!data) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-text-secondary">Failed to load users</p>
        </CardContent>
      </Card>
    )
  }

  const totalPages = Math.ceil(data.total / limit)

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <CardTitle>Users ({data.total})</CardTitle>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm text-text-secondary whitespace-nowrap">
              Page {page + 1} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
              disabled={page >= totalPages - 1}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {data.users.map((user) => (
            <div
              key={user.id}
              className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 rounded-lg border border-surface-elevated hover:border-primary/50 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1 min-w-0">
                  <p className="font-medium text-text-primary truncate min-w-0">{user.email}</p>
                  {user.is_admin && (
                    <div title="Admin" className="shrink-0">
                      <Shield className="h-4 w-4 text-primary" />
                    </div>
                  )}
                  {!user.is_active && (
                    <Badge variant="error">Inactive</Badge>
                  )}
                </div>
                {user.full_name && (
                  <p className="text-sm text-text-secondary truncate">{user.full_name}</p>
                )}
                <p className="text-xs text-text-tertiary mt-1">
                  Joined {formatDateTime(user.created_at)} •{' '}
                  {user.analyses_used}/{user.analyses_limit} analyses •{' '}
                  {user.watchlist_count} watchlist
                </p>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                {/* Tier selector */}
                <select
                  value={user.tier}
                  onChange={(e) => handleTierChange(user.id, e.target.value)}
                  disabled={isUpdating}
                  className="px-3 py-1.5 rounded-md border border-surface-elevated bg-surface text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="starter">Starter</option>
                  <option value="investor">Investor</option>
                  <option value="trader">Trader</option>
                </select>

                {/* Current tier badge */}
                <Badge variant={
                  user.tier === 'trader' ? 'success' :
                  user.tier === 'investor' ? 'secondary' : 'warning'
                }>
                  {user.tier}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
