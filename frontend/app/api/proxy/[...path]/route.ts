import { NextRequest, NextResponse } from 'next/server'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://research-swarm.vercel.app'

// Analysis can take 4+ minutes — allow up to 10 minutes
const LONG_TIMEOUT_MS = 600_000

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params
  const apiPath = path.join('/')
  const searchParams = request.nextUrl.searchParams.toString()
  const url = `${API_URL}/api/${apiPath}${searchParams ? `?${searchParams}` : ''}`

  try {
    // Forward Authorization header if present
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    }
    const authHeader = request.headers.get('authorization')
    if (authHeader) {
      headers['Authorization'] = authHeader
    }

    const response = await fetch(url, {
      method: 'GET',
      headers,
      signal: AbortSignal.timeout(LONG_TIMEOUT_MS),
    })

    // Handle binary responses (PDF, etc.)
    const contentType = response.headers.get('content-type') || ''
    if (contentType.includes('application/pdf')) {
      const arrayBuffer = await response.arrayBuffer()
      return new NextResponse(arrayBuffer, {
        status: response.status,
        headers: {
          'Content-Type': 'application/pdf',
          'Content-Disposition': response.headers.get('Content-Disposition') || '',
        },
      })
    }

    // Try to parse as JSON, handle non-JSON responses
    let data
    try {
      const text = await response.text()
      if (!text) {
        data = {}
      } else if (contentType.includes('application/json')) {
        data = JSON.parse(text)
      } else {
        // Non-JSON response (likely HTML error page)
        console.error('[proxy GET]', apiPath, `Non-JSON response (${response.status}):`, text.substring(0, 200))
        return NextResponse.json(
          { error: `Backend returned non-JSON response: ${text.substring(0, 100)}` },
          { status: response.status || 500 }
        )
      }
    } catch (parseError) {
      console.error('[proxy GET]', apiPath, 'JSON parse error:', parseError)
      return NextResponse.json(
        { error: 'Failed to parse backend response' },
        { status: 500 }
      )
    }

    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    console.error('[proxy GET]', apiPath, error)
    return NextResponse.json(
      { error: 'Failed to fetch from backend API' },
      { status: 500 }
    )
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params
  const apiPath = path.join('/')
  const url = `${API_URL}/api/${apiPath}`

  try {
    const body = await request.json()

    // Forward Authorization header if present
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    }
    const authHeader = request.headers.get('authorization')
    if (authHeader) {
      headers['Authorization'] = authHeader
    }

    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(LONG_TIMEOUT_MS),
    })

    // Try to parse as JSON, handle non-JSON responses
    const contentType = response.headers.get('content-type') || ''
    let data
    try {
      const text = await response.text()
      if (!text) {
        data = {}
      } else if (contentType.includes('application/json')) {
        data = JSON.parse(text)
      } else {
        console.error('[proxy POST]', apiPath, `Non-JSON response (${response.status}):`, text.substring(0, 200))
        return NextResponse.json(
          { error: `Backend returned non-JSON response: ${text.substring(0, 100)}` },
          { status: response.status || 500 }
        )
      }
    } catch (parseError) {
      console.error('[proxy POST]', apiPath, 'JSON parse error:', parseError)
      return NextResponse.json(
        { error: 'Failed to parse backend response' },
        { status: 500 }
      )
    }

    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    console.error('[proxy POST]', apiPath, error)
    return NextResponse.json(
      { error: 'Failed to fetch from backend API' },
      { status: 500 }
    )
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params
  const apiPath = path.join('/')
  const url = `${API_URL}/api/${apiPath}`

  try {
    // Forward Authorization header if present
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    }
    const authHeader = request.headers.get('authorization')
    if (authHeader) {
      headers['Authorization'] = authHeader
    }

    const response = await fetch(url, {
      method: 'DELETE',
      headers,
    })

    if (response.status === 204) {
      return new NextResponse(null, { status: 204 })
    }

    // Try to parse as JSON, handle non-JSON responses
    const contentType = response.headers.get('content-type') || ''
    let data
    try {
      const text = await response.text()
      if (!text) {
        data = {}
      } else if (contentType.includes('application/json')) {
        data = JSON.parse(text)
      } else {
        console.error('[proxy DELETE]', apiPath, `Non-JSON response (${response.status}):`, text.substring(0, 200))
        return NextResponse.json(
          { error: `Backend returned non-JSON response: ${text.substring(0, 100)}` },
          { status: response.status || 500 }
        )
      }
    } catch (parseError) {
      console.error('[proxy DELETE]', apiPath, 'JSON parse error:', parseError)
      return NextResponse.json(
        { error: 'Failed to parse backend response' },
        { status: 500 }
      )
    }

    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to fetch from backend API' },
      { status: 500 }
    )
  }
}
