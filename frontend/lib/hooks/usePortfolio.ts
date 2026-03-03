import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api/client'
import type { Portfolio, PortfolioListResponse, ActionFeed } from '@/types/api'

/**
 * usePortfolio — fetches the user's portfolio(s).
 * Returns an array of portfolios (usually 1 for Starter/Investor).
 */
export function usePortfolio(enabled = true) {
  return useQuery<PortfolioListResponse>({
    queryKey: ['portfolios'],
    queryFn: () => apiClient.getPortfolios(),
    staleTime: 1000 * 60 * 2,
    retry: 1,
    enabled,
  })
}

/**
 * usePortfolioDetail — fetches a single portfolio with positions.
 */
export function usePortfolioDetail(portfolioId: string | null) {
  return useQuery<Portfolio>({
    queryKey: ['portfolio', portfolioId],
    queryFn: () => apiClient.getPortfolio(portfolioId!),
    staleTime: 1000 * 60 * 2,
    enabled: !!portfolioId,
  })
}

/**
 * usePortfolioActions — fetches the action feed for a portfolio.
 */
export function usePortfolioActions(portfolioId: string | null, status?: string) {
  return useQuery<ActionFeed>({
    queryKey: ['portfolio-actions', portfolioId, status],
    queryFn: () => apiClient.getPortfolioActions(portfolioId!, status),
    staleTime: 1000 * 60 * 1,
    enabled: !!portfolioId,
  })
}

/**
 * usePortfolioPosition — find a specific ticker's position in the user's primary portfolio.
 * Useful for report pages that need portfolio context.
 */
export function usePortfolioPosition(ticker: string | null) {
  const { data } = usePortfolio()
  const portfolio = data?.portfolios?.[0]
  const position = portfolio?.positions?.find(
    p => p.ticker.toUpperCase() === ticker?.toUpperCase()
  )
  return { portfolio, position }
}

/**
 * useMarkAction — mutation to mark an action as executed or ignored.
 */
export function useMarkAction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      portfolioId,
      actionId,
      status,
      overrideWeight,
    }: {
      portfolioId: string
      actionId: string
      status: 'executed' | 'ignored'
      overrideWeight?: number
    }) => apiClient.markAction(portfolioId, actionId, status, overrideWeight),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio-actions'] })
      queryClient.invalidateQueries({ queryKey: ['portfolios'] })
      queryClient.invalidateQueries({ queryKey: ['portfolio'] })
    },
  })
}

/**
 * useAddPosition — mutation to add a new position to an existing portfolio.
 */
export function useAddPosition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      portfolioId,
      ticker,
      weight,
      costBasis,
      shares,
    }: {
      portfolioId: string
      ticker: string
      weight: number
      costBasis?: number
      shares?: number
    }) => apiClient.addPosition(portfolioId, ticker, weight, costBasis, shares),
    onSuccess: (_res, { portfolioId }) => {
      queryClient.invalidateQueries({ queryKey: ['portfolio', portfolioId] })
      queryClient.invalidateQueries({ queryKey: ['portfolios'] })
    },
  })
}

/**
 * useUpdatePosition — mutation to update a position's weight, cost basis, or shares.
 */
export function useUpdatePosition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      portfolioId,
      ticker,
      data,
    }: {
      portfolioId: string
      ticker: string
      data: { weight?: number; cost_basis?: number; shares?: number }
    }) => apiClient.updatePosition(portfolioId, ticker, data),
    onSuccess: (_res, { portfolioId }) => {
      queryClient.invalidateQueries({ queryKey: ['portfolio', portfolioId] })
      queryClient.invalidateQueries({ queryKey: ['portfolios'] })
    },
  })
}

/**
 * useRemovePosition — mutation to delete a position from a portfolio.
 */
export function useRemovePosition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      portfolioId,
      ticker,
    }: {
      portfolioId: string
      ticker: string
    }) => apiClient.removePosition(portfolioId, ticker),
    onSuccess: (_res, { portfolioId }) => {
      queryClient.invalidateQueries({ queryKey: ['portfolio', portfolioId] })
      queryClient.invalidateQueries({ queryKey: ['portfolios'] })
    },
  })
}

/**
 * useTriggerEngine — mutation to manually trigger an engine run.
 */
export function useTriggerEngine() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      portfolioId,
      cycleType = 'monthly',
    }: {
      portfolioId: string
      cycleType?: string
    }) => apiClient.triggerEngineRun(portfolioId, cycleType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio-actions'] })
      queryClient.invalidateQueries({ queryKey: ['portfolios'] })
    },
  })
}
