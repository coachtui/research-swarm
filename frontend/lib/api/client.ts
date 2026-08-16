// Type-safe API client for DVRG Backend

import type {
  AnalyzeRequest,
  AnalyzeResponse,
  RunResponse,
  RunListResponse,
  ApiError as ApiErrorType,
  WatchlistResponse,
  AddToWatchlistRequest,
  UpdateNotesRequest,
  RefreshWatchlistResponse,
  WatchlistStatsResponse,
  QuotaData,
  PlatformMetrics,
  UsersListResponse,
  AnalysesListResponse,
  UpdateTierRequest,
  CostSummary,
  RevenueTimeSeries,
  UserInfo,
  MarketOutlookResponse,
  EngineReportEntry,
  WeekResponse,
  WeeklyBatchRunSummary,
  WeeklyBatchRunDetail,
  EntitlementsResponse,
  DeploymentUpdateResponse,
  EligibilityStressTestResponse,
  EligibilityRollingSimResponse,
  OpportunityDistributionResponse,
  ThresholdCalibrationResponse,
  CalibrationNote,
  CalibrationNoteListResponse,
  Portfolio,
  PortfolioListResponse,
  ActionFeed,
  PortfolioIntelligence,
  RefreshPricesResponse,
  ExecuteActionResponse,
  CancelActionResponse,
  UpdateCashResponse,
} from '@/types/api'
import type {
  LeaderboardResponse,
  TrackRecordResponse,
  WeeklySignalPublic,
} from '@/types/weekly-signals'
import type { AnalysisReport } from '@/types/report'

class ApiClient {
  private baseUrl: string
  private authToken?: string
  private tokenGetter?: () => Promise<string | null>
  private useProxy: boolean = false

  // Token cache — avoid hammering Clerk on every poll request
  private _cachedToken: string | null = null
  private _cachedTokenExp: number = 0
  private _tokenPromise: Promise<string | null> | null = null

  constructor(baseUrl?: string) {
    // Use local proxy in development to avoid CORS issues
    if (typeof window !== 'undefined' && window.location.hostname === 'localhost') {
      this.baseUrl = '/api/proxy'
      this.useProxy = true
    } else {
      this.baseUrl = baseUrl || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      this.useProxy = false
    }
  }

  setAuthToken(token: string) {
    this.authToken = token
  }

  // Device ID for anti-abuse tracking on free tier
  private _deviceId: string | null = null

  getDeviceId(): string {
    if (this._deviceId) return this._deviceId
    if (typeof window === 'undefined') return ''
    let id = localStorage.getItem('dvrg_device_id')
    if (!id) {
      // Generate a secure random UUID-like identifier
      id = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
        const r = (Math.random() * 16) | 0
        return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
      })
      localStorage.setItem('dvrg_device_id', id)
    }
    this._deviceId = id
    return id
  }

  // Preferred: store Clerk's getToken function so each request gets a fresh token
  setTokenGetter(getter: () => Promise<string | null>) {
    this.tokenGetter = getter
    // Invalidate cache when a new getter is registered (e.g. user switches)
    this._cachedToken = null
    this._cachedTokenExp = 0
    this._tokenPromise = null
  }

  /**
   * Returns a valid JWT, using a client-side cache keyed on the JWT `exp` claim.
   * Only one in-flight refresh request is allowed at a time (deduplication).
   * This prevents the thundering-herd of Clerk 429s when many concurrent API
   * calls (e.g. polling + multiple components) all trigger getToken simultaneously.
   */
  private async _resolveToken(): Promise<string | null> {
    const now = Date.now()
    // Return cached token if it has >30 s of life left
    if (this._cachedToken && now < this._cachedTokenExp - 30_000) {
      return this._cachedToken
    }

    // Deduplicate: reuse an in-flight refresh promise if one already exists
    if (!this._tokenPromise) {
      this._tokenPromise = this._fetchFreshToken().finally(() => {
        this._tokenPromise = null
      })
    }
    return this._tokenPromise
  }

  private async _fetchFreshToken(): Promise<string | null> {
    const token = this.tokenGetter
      ? (await this.tokenGetter()) ?? this.authToken
      : this.authToken

    if (token) {
      // Parse JWT exp claim (second segment, base64url-encoded JSON)
      try {
        const parts = token.split('.')
        if (parts.length === 3) {
          const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')))
          if (payload.exp) {
            this._cachedToken = token
            this._cachedTokenExp = payload.exp * 1000 // seconds → ms
          }
        }
      } catch {
        // Non-standard token or SSR env — skip caching, still return token
      }
    }

    return token ?? null
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = await this._resolveToken()

    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    }

    // Remove /api/ prefix when using proxy (proxy adds it back)
    const cleanEndpoint = this.useProxy ? endpoint.replace(/^\/api\//, '/') : endpoint
    const url = `${this.baseUrl}${cleanEndpoint}`

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      })

      if (!response.ok) {
        let errorMessage = 'Request failed'
        try {
          const error = await response.json()
          errorMessage = error.detail || error.message || errorMessage
        } catch {
          errorMessage = response.statusText || errorMessage
        }

        throw {
          status: response.status,
          message: errorMessage,
          name: 'ApiError',
        } as ApiErrorType
      }

      return response.json()
    } catch (error) {
      if ((error as any).status) {
        throw error
      }
      throw {
        status: 0,
        message: 'Network error. Please check your connection.',
        name: 'ApiError',
      } as ApiErrorType
    }
  }

  // Health check
  async healthCheck(): Promise<{ status: string }> {
    return this.request('/api/health')
  }

  // Auth endpoints
  async getCurrentUser(): Promise<UserInfo> {
    return this.request('/api/auth/me')
  }

  /**
   * Fetch server-resolved feature flags and quota limits.
   * The backend applies admin override and Stripe inactive-status downgrade,
   * so the client receives the correct effective entitlements without
   * having to replicate that logic.
   */
  async getEntitlements(): Promise<EntitlementsResponse> {
    return this.request('/api/entitlements')
  }

  /**
   * Idempotently ensure the user's Neon entitlement rows exist.
   * Call once on first signed-in load of /analyze to handle missed Clerk webhooks.
   */
  async ensureEntitlements(): Promise<{ ensured: boolean; tier: string }> {
    return this.request('/api/entitlements/ensure', { method: 'POST' })
  }

  // Analysis endpoints
  async analyzeStock(request: AnalyzeRequest): Promise<AnalyzeResponse> {
    const deviceId = this.getDeviceId()
    return this.request('/api/analyze', {
      method: 'POST',
      body: JSON.stringify(request),
      headers: {
        ...(deviceId && { 'X-Device-ID': deviceId }),
      },
    })
  }

  async getAnalysis(runId: string): Promise<RunResponse> {
    return this.request(`/api/runs/${runId}`)
  }

  /**
   * Phase D: fetch the persisted AnalysisReport (built once at write time,
   * served verbatim). Returns null for runs analyzed before Phase C or when
   * the user's tier lacks full-report access — callers fall back to
   * full_output-derived rendering.
   */
  async getAnalysisReport(runId: string): Promise<AnalysisReport | null> {
    try {
      return await this.request<AnalysisReport>(`/api/runs/${runId}/report`)
    } catch (error) {
      const status = (error as { status?: number }).status
      if (status === 404 || status === 403) return null
      throw error
    }
  }

  /** Public — no auth required. Returns the latest completed NVDA run for the example report. */
  async getPreviewNvda(): Promise<RunResponse> {
    const cleanEndpoint = this.useProxy ? '/preview/nvda' : '/api/preview/nvda'
    const url = `${this.baseUrl}${cleanEndpoint}`
    const response = await fetch(url, { headers: { 'Content-Type': 'application/json' } })
    if (!response.ok) throw { status: response.status, message: 'Preview unavailable', name: 'ApiError' }
    return response.json()
  }

  async getAnalysisHistory(
    limit = 20,
    offset = 0,
    status?: string
  ): Promise<RunListResponse> {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
      ...(status && { status }),
    })
    return this.request(`/api/runs?${params}`)
  }

  async deleteAnalysis(runId: string): Promise<void> {
    return this.request(`/api/runs/${runId}`, {
      method: 'DELETE',
    })
  }

  // Watchlist endpoints
  async getWatchlist(): Promise<WatchlistResponse> {
    return this.request('/api/watchlist')
  }

  async addToWatchlist(request: AddToWatchlistRequest): Promise<{ success: boolean; item: any }> {
    return this.request('/api/watchlist', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async removeFromWatchlist(ticker: string): Promise<{ success: boolean; ticker: string }> {
    return this.request(`/api/watchlist/${ticker}`, {
      method: 'DELETE',
    })
  }

  async refreshWatchlistItem(ticker: string): Promise<RefreshWatchlistResponse> {
    return this.request(`/api/watchlist/${ticker}/refresh`, {
      method: 'POST',
    })
  }

  async updateWatchlistNotes(ticker: string, request: UpdateNotesRequest): Promise<{ success: boolean }> {
    return this.request(`/api/watchlist/${ticker}/notes`, {
      method: 'PATCH',
      body: JSON.stringify(request),
    })
  }

  async getWatchlistStats(): Promise<WatchlistStatsResponse> {
    return this.request('/api/watchlist/stats')
  }

  // Quota endpoint
  async getQuota(): Promise<QuotaData> {
    return this.request('/api/usage')
  }

  // Analysis history endpoints
  async getRuns(limit = 20, offset = 0, status?: string): Promise<RunListResponse> {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
      ...(status && { status }),
    })
    return this.request(`/api/runs?${params}`)
  }

  async getRun(runId: string): Promise<RunResponse> {
    return this.request(`/api/runs/${runId}`)
  }

  // Admin endpoints
  async getAdminMetrics(): Promise<PlatformMetrics> {
    return this.request('/api/admin/metrics')
  }

  async getAdminUsers(limit = 50, offset = 0): Promise<UsersListResponse> {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    })
    return this.request(`/api/admin/users?${params}`)
  }

  async updateUserTier(userId: string, request: UpdateTierRequest): Promise<{ success: boolean }> {
    return this.request(`/api/admin/users/${userId}/tier`, {
      method: 'PATCH',
      body: JSON.stringify(request),
    })
  }

  async getAdminAnalyses(limit = 100, ticker?: string): Promise<AnalysesListResponse> {
    const params = new URLSearchParams({
      limit: String(limit),
      ...(ticker && { ticker }),
    })
    return this.request(`/api/admin/analyses?${params}`)
  }

  async getCostSummary(): Promise<CostSummary> {
    return this.request('/api/admin/costs')
  }

  async getAdminRevenue(): Promise<RevenueTimeSeries> {
    return this.request('/api/admin/revenue')
  }

  async getMarketOutlook(): Promise<MarketOutlookResponse> {
    return this.request('/api/autopilot/outlook')
  }

  async getEngineReports(params?: { type?: string; severity?: string; limit?: number }): Promise<EngineReportEntry[]> {
    const q = new URLSearchParams()
    if (params?.type) q.set('type', params.type)
    if (params?.severity) q.set('severity', params.severity)
    if (params?.limit) q.set('limit', String(params.limit))
    const suffix = q.toString() ? `?${q.toString()}` : ''
    return this.request(`/api/autopilot/reports${suffix}`)
  }

  async getWeek(week?: string): Promise<WeekResponse> {
    const suffix = week ? `?week=${encodeURIComponent(week)}` : ''
    return this.request(`/api/autopilot/week${suffix}`)
  }

  async getWeeklyBatchRuns(limit = 12): Promise<WeeklyBatchRunSummary[]> {
    return this.request(`/api/autopilot/batch-runs?limit=${limit}`)
  }

  async getWeeklyBatchRunDetail(runDate?: string): Promise<WeeklyBatchRunDetail> {
    const suffix = runDate ? `?run_date=${encodeURIComponent(runDate)}` : ''
    return this.request(`/api/autopilot/batch-runs/detail${suffix}`)
  }

  // Stripe subscription methods
  async createCheckoutSession(priceId: string): Promise<{ checkout_url: string }> {
    return this.request('/api/stripe/create-checkout-session', {
      method: 'POST',
      body: JSON.stringify({ price_id: priceId }),
    })
  }

  async createPortalSession(): Promise<{ portal_url: string }> {
    return this.request('/api/stripe/create-portal-session', {
      method: 'POST',
    })
  }

  async createBoostSession(): Promise<{ checkout_url: string; warn_expiry?: boolean; days_remaining?: number }> {
    return this.request('/api/stripe/create-boost-session', {
      method: 'POST',
    })
  }

  // Deployment endpoints
  async getDeploymentUpdate(): Promise<DeploymentUpdateResponse> {
    return this.request('/api/deployment/structural-update')
  }

  async getAdminDeploymentUpdate(): Promise<DeploymentUpdateResponse> {
    return this.request('/api/deployment/structural-update/admin')
  }

  async getEligibilityStressTest(): Promise<EligibilityStressTestResponse> {
    return this.request('/api/deployment/eligibility-stress-test/admin')
  }

  async getEligibilityRollingSim(): Promise<EligibilityRollingSimResponse> {
    return this.request('/api/deployment/eligibility-rolling-sim/admin')
  }

  async getOpportunityDistribution(): Promise<OpportunityDistributionResponse> {
    return this.request('/api/deployment/opportunity-distribution/admin')
  }

  async getCalibration(percentileGate = 60): Promise<ThresholdCalibrationResponse> {
    return this.request(`/api/deployment/calibration/admin?percentile_gate=${percentileGate}`)
  }

  async saveCalibrationNote(text: string): Promise<CalibrationNote> {
    return this.request('/api/deployment/calibration/notes/admin', {
      method: 'POST',
      body: JSON.stringify({ text }),
    })
  }

  async getCalibrationNotes(): Promise<CalibrationNoteListResponse> {
    return this.request('/api/deployment/calibration/notes/admin')
  }

  // ── Portfolio Engine ────────────────────────────────────────────────────

  async getPortfolios(): Promise<PortfolioListResponse> {
    return this.request('/api/portfolio')
  }

  async getPortfolio(id: string): Promise<Portfolio> {
    return this.request(`/api/portfolio/${id}`)
  }

  async createPortfolio(name = 'Core', mandate = 'compounder'): Promise<Portfolio> {
    return this.request('/api/portfolio', {
      method: 'POST',
      body: JSON.stringify({ name, mandate }),
    })
  }

  async addPosition(portfolioId: string, ticker: string, shares: number, costBasis?: number, targetWeight?: number): Promise<unknown> {
    return this.request(`/api/portfolio/${portfolioId}/positions`, {
      method: 'POST',
      body: JSON.stringify({ ticker, shares, cost_basis: costBasis, target_weight: targetWeight }),
    })
  }

  async updatePosition(portfolioId: string, ticker: string, data: { target_weight?: number; cost_basis?: number; shares?: number }): Promise<unknown> {
    return this.request(`/api/portfolio/${portfolioId}/positions/${ticker}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  }

  async removePosition(portfolioId: string, ticker: string): Promise<unknown> {
    return this.request(`/api/portfolio/${portfolioId}/positions/${ticker}`, {
      method: 'DELETE',
    })
  }

  async getPortfolioActions(portfolioId: string, status?: string): Promise<ActionFeed> {
    const params = status ? `?status=${status}` : ''
    return this.request(`/api/portfolio/${portfolioId}/actions${params}`)
  }

  async markAction(portfolioId: string, actionId: string, status: 'executed' | 'ignored', overrideWeight?: number): Promise<unknown> {
    return this.request(`/api/portfolio/${portfolioId}/actions/${actionId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status, override_weight: overrideWeight }),
    })
  }

  async triggerEngineRun(portfolioId: string, cycleType = 'monthly'): Promise<unknown> {
    return this.request(`/api/portfolio/${portfolioId}/engine/run?cycle_type=${cycleType}`, {
      method: 'POST',
    })
  }

  async getPortfolioIntelligence(portfolioId: string): Promise<PortfolioIntelligence> {
    return this.request(`/api/portfolio/${portfolioId}/intelligence`)
  }

  async refreshPrices(portfolioId: string): Promise<RefreshPricesResponse> {
    return this.request(`/api/portfolio/${portfolioId}/refresh-prices`, { method: 'POST' })
  }

  async updateCash(portfolioId: string, amount: number): Promise<UpdateCashResponse> {
    return this.request(`/api/portfolio/${portfolioId}/cash`, {
      method: 'POST',
      body: JSON.stringify({ amount }),
    })
  }

  async rebalancePortfolio(portfolioId: string): Promise<{ actions_created: number; portfolio_id: string }> {
    return this.request(`/api/portfolio/${portfolioId}/rebalance`, { method: 'POST' })
  }

  async resetThesis(portfolioId: string): Promise<{ reset: boolean; portfolio_id: string }> {
    return this.request(`/api/portfolio/${portfolioId}/reset-thesis`, { method: 'POST' })
  }

  async executeAction(actionId: string): Promise<ExecuteActionResponse> {
    return this.request(`/api/actions/${actionId}/execute`, { method: 'POST' })
  }

  async cancelAction(actionId: string): Promise<CancelActionResponse> {
    return this.request(`/api/actions/${actionId}/cancel`, { method: 'POST' })
  }

  // ── WeeklySignal endpoints ──────────────────────────────────────────────

  async getLeaderboard(limit = 25): Promise<LeaderboardResponse> {
    return this.request<LeaderboardResponse>(
      `/api/weekly-signals/leaderboard?limit=${limit}`
    )
  }

  async getTrackRecord(limit = 100): Promise<TrackRecordResponse> {
    return this.request<TrackRecordResponse>(
      `/api/weekly-signals/track-record?limit=${limit}`
    )
  }

  async getWeeklyPreview(ticker: string): Promise<WeeklySignalPublic> {
    return this.request<WeeklySignalPublic>(
      `/api/weekly-signals/preview/${encodeURIComponent(ticker.toUpperCase())}`
    )
  }
}

// Export singleton instance
export const apiClient = new ApiClient()

// Export class for custom instances
export { ApiClient }
