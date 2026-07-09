import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useMarketOutlook } from '@/lib/hooks/useAdmin'
import { formatDate, formatPercent } from '@/lib/utils/formatting'
import { AlertTriangle } from 'lucide-react'
import type {
  IndustryRotationFlag,
  MarketOutlookResponse,
  RotationFlag,
  SizeStyle,
  ThemeHistoryPoint,
  ThemeRotationFlag,
} from '@/types/api'

const REGIME_BADGE_VARIANT: Record<string, 'success' | 'warning' | 'error'> = {
  risk_on: 'success',
  neutral: 'warning',
  risk_off: 'error',
}

function regimeLabel(regime: string): string {
  return regime
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

function signedPct(value: number, decimals = 1): string {
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(decimals)}%`
}

function rotationLabel(flag: RotationFlag): string {
  return flag.direction === 'into'
    ? `Rotation into ${flag.sector} (${flag.etf})`
    : `Rotation out of ${flag.sector} (${flag.etf})`
}

function sizeStyleLabel(tag: SizeStyle['tag']): string {
  return tag
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

function industryRotationLabel(flag: IndustryRotationFlag): string {
  return flag.direction === 'into'
    ? `Rotation into ${flag.industry} (${flag.etf})`
    : `Rotation out of ${flag.industry} (${flag.etf})`
}

function themeRotationLabel(flag: ThemeRotationFlag): string {
  return flag.direction === 'into'
    ? `Rotation into ${flag.theme} (${flag.etf})`
    : `Rotation out of ${flag.theme} (${flag.etf})`
}

function ThemeSparkline({ points }: { points: ThemeHistoryPoint[] }) {
  if (points.length < 2) return null
  const scores = points.map((p) => p.score)
  const min = Math.min(...scores)
  const max = Math.max(...scores)
  const span = max - min || 1
  const coords = points
    .map((p, i) => `${(i / (points.length - 1)) * 60},${18 - ((p.score - min) / span) * 16}`)
    .join(' ')
  return (
    <svg width="60" height="20" className="text-primary shrink-0" aria-hidden="true">
      <polyline points={coords} fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  )
}

export function MarketOutlookPanel() {
  const { data, isLoading, error } = useMarketOutlook()

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Market Outlook</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error && (error as any).status === 404) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-text-secondary">
            No outlook yet — first one generates Sunday night.
          </p>
        </CardContent>
      </Card>
    )
  }

  if (error || !data) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-text-secondary">Failed to load market outlook</p>
        </CardContent>
      </Card>
    )
  }

  return <MarketOutlookContent outlook={data} />
}

function MarketOutlookContent({ outlook }: { outlook: MarketOutlookResponse }) {
  const {
    run_date,
    regime,
    regime_mechanical,
    strategist_override,
    strategist_status,
    conviction,
    sector_rankings,
    rotation_flags,
    breadth,
    reasoning,
    industry_rankings,
    industry_rotations,
    size_style,
    theme_rankings,
    theme_rotations,
    theme_missing,
    theme_history,
  } = outlook

  const regimeVariant = REGIME_BADGE_VARIANT[regime] ?? 'secondary'

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <CardTitle>Market Outlook</CardTitle>
            <span className="text-sm text-text-secondary">
              Week of {formatDate(run_date)}
            </span>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <Badge variant={regimeVariant}>{regimeLabel(regime)}</Badge>
            <div>
              <span className="text-sm text-text-secondary mr-1">Conviction:</span>
              <span className="text-sm font-medium text-text-primary">
                {conviction === null ? 'n/a' : formatPercent(conviction * 100, 0)}
              </span>
            </div>
            {size_style && (
              <Badge variant="secondary">{sizeStyleLabel(size_style.tag)}</Badge>
            )}
          </div>

          {strategist_override && (
            <p className="text-xs text-text-tertiary">
              Mechanical regime: {regimeLabel(regime_mechanical)} — overridden by strategist
            </p>
          )}

          {strategist_status !== 'ok' && (
            <div className="flex items-center gap-2 text-xs text-warning">
              <AlertTriangle className="h-3.5 w-3.5" />
              <span>Strategist fallback in use (status: {strategist_status})</span>
            </div>
          )}

          {reasoning && (
            <p className="text-sm text-text-secondary leading-relaxed">{reasoning}</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Sector Rankings</CardTitle>
        </CardHeader>
        <CardContent>
          {sector_rankings.length === 0 ? (
            <p className="text-sm text-text-secondary">No sector ranking data.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-surface-elevated text-text-secondary uppercase tracking-wide">
                    <th className="text-left py-2 pr-3 font-medium">Rank</th>
                    <th className="text-left py-2 px-2 font-medium">Sector</th>
                    <th className="text-right py-2 px-2 font-medium">1m Rank</th>
                    <th className="text-right py-2 px-2 font-medium">3m Rank</th>
                    <th className="text-right py-2 px-2 font-medium">Rank Δ</th>
                    <th className="text-right py-2 pl-2 font-medium">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {sector_rankings.map((row, i) => (
                    <tr
                      key={row.etf}
                      className="border-b border-surface-elevated/30"
                    >
                      <td className="py-2 pr-3 text-text-primary font-medium">{i + 1}</td>
                      <td className="py-2 px-2 text-text-primary">
                        {row.sector} <span className="text-text-tertiary">({row.etf})</span>
                      </td>
                      <td className="text-right py-2 px-2 text-text-secondary">{row.rank_1m}</td>
                      <td className="text-right py-2 px-2 text-text-secondary">{row.rank_3m}</td>
                      <td
                        className={`text-right py-2 px-2 font-medium ${
                          row.rank_change > 0
                            ? 'text-success'
                            : row.rank_change < 0
                              ? 'text-error'
                              : 'text-text-secondary'
                        }`}
                      >
                        {row.rank_change > 0 ? `+${row.rank_change}` : row.rank_change}
                      </td>
                      <td className="text-right py-2 pl-2 text-text-secondary">
                        {row.score.toFixed(4)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {industry_rankings && industry_rankings.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Leading Industries</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <ul className="space-y-1">
              {industry_rankings.slice(0, 5).map((row, i) => (
                <li key={row.etf} className="text-sm text-text-primary">
                  <span className="font-medium">{i + 1}.</span> {row.industry}{' '}
                  <span className="text-text-tertiary">({row.etf})</span>
                  <span
                    className={`ml-2 text-xs font-medium ${
                      row.rank_change > 0
                        ? 'text-success'
                        : row.rank_change < 0
                          ? 'text-error'
                          : 'text-text-secondary'
                    }`}
                  >
                    {row.rank_change > 0 ? `+${row.rank_change}` : row.rank_change}
                  </span>
                  <span className="ml-2 text-xs text-text-secondary">
                    {row.score.toFixed(4)}
                  </span>
                </li>
              ))}
            </ul>
            {industry_rotations && industry_rotations.length > 0 && (
              <ul className="space-y-1">
                {industry_rotations.map((flag) => (
                  <li
                    key={flag.etf}
                    className={`text-sm ${flag.direction === 'into' ? 'text-success' : 'text-error'}`}
                  >
                    {industryRotationLabel(flag)}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}

      {theme_rankings && theme_rankings.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Leading Themes</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-2">
              {theme_rankings.map((t, i) => (
                <div key={t.slug} className="flex items-center justify-between gap-3 text-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-text-secondary w-5 shrink-0">{i + 1}.</span>
                    <span className="text-text-primary truncate">{t.theme}</span>
                    <span className="text-text-tertiary text-xs shrink-0">
                      {t.constituent_count} names
                    </span>
                    {t.rank_change >= 5 && <Badge variant="success">rotating in</Badge>}
                    {t.rank_change <= -5 && <Badge variant="error">rotating out</Badge>}
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <ThemeSparkline points={theme_history?.[t.slug] ?? []} />
                    <span className="tabular-nums text-text-secondary">
                      {t.score >= 0 ? '+' : ''}
                      {t.score.toFixed(4)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
            {theme_rotations && theme_rotations.length > 0 && (
              <ul className="space-y-1">
                {theme_rotations.map((flag) => (
                  <li
                    key={flag.etf}
                    className={`text-sm ${flag.direction === 'into' ? 'text-success' : 'text-error'}`}
                  >
                    {themeRotationLabel(flag)}
                  </li>
                ))}
              </ul>
            )}
            {theme_missing && theme_missing.length > 0 && (
              <p className="text-xs text-text-secondary pt-1">
                Not ranked: {theme_missing.map((m) => `${m.slug} (${m.reason})`).join('; ')}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Rotation &amp; Breadth</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {rotation_flags.length === 0 ? (
            <p className="text-sm text-text-secondary">No rotation flags this week.</p>
          ) : (
            <ul className="space-y-1">
              {rotation_flags.map((flag) => (
                <li
                  key={flag.etf}
                  className={`text-sm ${flag.direction === 'into' ? 'text-success' : 'text-error'}`}
                >
                  {rotationLabel(flag)}
                </li>
              ))}
            </ul>
          )}

          <p className="text-sm text-text-secondary">
            {breadth.pct_above_200dma === null
              ? 'Breadth: n/a'
              : `${breadth.pct_above_200dma}% of sectors above 200dma`}
            {breadth.equal_weight_trend_3m !== null && (
              <> • RSP/SPY 3m trend: {signedPct(breadth.equal_weight_trend_3m)}</>
            )}
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
