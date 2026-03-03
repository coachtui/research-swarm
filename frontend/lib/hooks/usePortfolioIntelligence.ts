import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api/client'
import type { PortfolioIntelligence } from '@/types/api'

/**
 * usePortfolioIntelligence — fetches the Portfolio Intelligence overlay for a portfolio.
 *
 * Stale time is 5 minutes — scores are derived from existing StockResult data and
 * don't change unless new analyses are run.
 */
export function usePortfolioIntelligence(portfolioId: string | null) {
  return useQuery<PortfolioIntelligence>({
    queryKey: ['portfolio-intelligence', portfolioId],
    queryFn: () => apiClient.getPortfolioIntelligence(portfolioId!),
    staleTime: 1000 * 60 * 5,
    retry: 1,
    enabled: !!portfolioId,
  })
}
