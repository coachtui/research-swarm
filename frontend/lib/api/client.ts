// Type-safe API client for DVRG Backend

import type {
  AnalyzeRequest,
  AnalyzeResponse,
  RunResponse,
  RunListResponse,
  ApiError as ApiErrorType,
} from '@/types/api'

class ApiClient {
  private baseUrl: string
  private authToken?: string
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

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...(this.authToken && { Authorization: `Bearer ${this.authToken}` }),
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
}

// Export singleton instance
export const apiClient = new ApiClient()

// Export class for custom instances
export { ApiClient }
