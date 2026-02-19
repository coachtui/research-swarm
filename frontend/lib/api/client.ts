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
  UserInfo,
} from '@/types/api'

class ApiClient {
  private baseUrl: string
  private authToken?: string
  private tokenGetter?: () => Promise<string | null>
  private useProxy: boolean = false

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

  // Preferred: store Clerk's getToken function so each request gets a fresh token
  setTokenGetter(getter: () => Promise<string | null>) {
    this.tokenGetter = getter
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    // Always fetch a fresh token if a getter is available (Clerk auto-refreshes)
    const token = this.tokenGetter
      ? (await this.tokenGetter()) ?? this.authToken
      : this.authToken

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

  // Analysis endpoints
  async analyzeStock(request: AnalyzeRequest): Promise<AnalyzeResponse> {
    return this.request('/api/analyze', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async getAnalysis(runId: string): Promise<RunResponse> {
    return this.request(`/api/runs/${runId}`)
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
}

// Export singleton instance
export const apiClient = new ApiClient()

// Export class for custom instances
export { ApiClient }
