# DVRG Frontend

Customer-facing web application for DVRG stock analysis platform, built with Next.js 14 and the Robinhood-inspired design aesthetic.

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS with custom #00D9B5 brand color
- **Components**: shadcn/ui (Radix primitives)
- **State Management**: TanStack Query (React Query)
- **Charts**: Recharts
- **Payments**: Stripe
- **Email**: Resend.com
- **Hosting**: Vercel

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Backend API deployed at https://research-swarm.vercel.app

### Installation

```bash
# Install dependencies
npm install

# Create environment file
cp .env.local.example .env.local
# Edit .env.local with your API URL and keys

# Run development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Environment Variables

```bash
# Required
NEXT_PUBLIC_API_URL=https://research-swarm.vercel.app

# Optional (for payments & email)
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
RESEND_API_KEY=re_...
```

## Project Structure

```
frontend/
├── app/                      # Next.js App Router pages
│   ├── page.tsx             # Landing page
│   ├── analyze/page.tsx     # Analysis request form
│   └── results/[run_id]/    # Results display
├── components/               # React components
│   ├── ui/                  # shadcn/ui primitives
│   ├── layout/              # Header, Footer
│   ├── landing/             # Landing page sections
│   ├── analyze/             # Analysis form components
│   └── results/             # Results display components
├── lib/                      # Utilities and hooks
│   ├── api/client.ts        # API client wrapper
│   ├── hooks/               # React hooks (useAnalysis, etc.)
│   └── utils/               # Formatting, errors
└── types/                    # TypeScript types
    └── api.ts               # API request/response types
```

## Key Features

- **Polling System**: Automatically polls backend every 5s during 4-minute analysis
- **Robinhood Aesthetic**: Dark mode with #00D9B5 teal accent color
- **Type-Safe API**: Full TypeScript coverage for backend integration
- **Responsive**: Mobile-first design
- **Real-time Updates**: Status changes reflected immediately

## Development

```bash
# Run dev server
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Lint code
npm run lint
```

## Deployment

Deploy to Vercel:

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel

# Deploy to production
vercel --prod
```

Set environment variables in Vercel dashboard.

## Color Palette

- **Primary**: #00D9B5 (DVRG Teal)
- **Background**: #0A0E1A (Dark)
- **Surface**: #1A1F2E (Card/Panel)
- **Success**: #10B981 (Bullish)
- **Warning**: #F59E0B (Caution)
- **Error**: #EF4444 (Bearish)

## API Integration

The frontend consumes the FastAPI backend with 3 main endpoints:

- `POST /api/analyze` - Submit analysis request
- `GET /api/runs` - List user's analyses
- `GET /api/runs/{run_id}` - Get detailed results

See `lib/api/client.ts` for implementation.

## License

Proprietary - DVRG
