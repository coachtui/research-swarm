import Link from 'next/link'
import { redirect } from 'next/navigation'
import { auth } from '@clerk/nextjs/server'
import { CheckCircle2, Mail, ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'

/**
 * /welcome/free — landing page for free-tier onboarding.
 *
 * Signed-out users see the value proposition + sign-up CTA.
 * Signed-in users are sent straight to /analyze (no point showing sign-up again).
 */
export default async function WelcomeFreePage() {
  const { userId } = await auth()
  if (userId) {
    redirect('/analyze')
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center py-16 px-4">
      <div className="max-w-lg w-full space-y-8">

        {/* Badge */}
        <div className="text-center">
          <span
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium text-primary"
            style={{ background: 'var(--accent-weak)', border: '1px solid var(--accent-border)' }}
          >
            Free — No credit card required
          </span>
        </div>

        {/* Headline */}
        <div className="text-center space-y-3">
          <h1 className="text-3xl md:text-4xl font-bold text-text-primary tracking-tight">
            Generate 2 full DVRG reports free
          </h1>
          <p className="text-text-secondary leading-relaxed">
            Same institutional-quality analysis as our Starter plan.
            No subscription needed to get started.
          </p>
        </div>

        {/* What's included */}
        <div
          className="rounded-xl p-5 space-y-3"
          style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}
        >
          <p className="text-xs font-semibold uppercase tracking-widest text-text-secondary">
            Each free report includes
          </p>
          <ul className="space-y-2.5">
            {[
              'Moat score breakdown (5 components)',
              'Investment thesis with Bull / Base / Bear scenarios',
              'VGM score + signal divergence detection',
              'Blended fair-value estimate (DCF + multiples)',
              'Capital allocation framework with position sizing',
            ].map((item) => (
              <li key={item} className="flex items-start gap-2.5">
                <CheckCircle2 className="h-4 w-4 text-success shrink-0 mt-0.5" />
                <span className="text-sm text-text-secondary">{item}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Email verification note */}
        <div
          className="flex items-start gap-3 rounded-lg px-4 py-3"
          style={{ background: 'var(--accent-weak)', border: '1px solid var(--accent-border)' }}
        >
          <Mail className="h-4 w-4 text-primary shrink-0 mt-0.5" />
          <p className="text-xs text-text-secondary leading-relaxed">
            <span className="font-medium text-text-primary">Verify your email</span> after
            signup to unlock your second free report.
          </p>
        </div>

        {/* CTAs */}
        <div className="space-y-3">
          <Link href="/sign-up?redirect_url=/analyze&intent=free" className="block">
            <Button size="lg" className="w-full">
              Create free account <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
          <Link href="/sign-in?redirect_url=/analyze" className="block">
            <Button size="lg" variant="ghost" className="w-full">
              Already have an account? Sign in
            </Button>
          </Link>
        </div>

        <p className="text-center text-xs text-text-tertiary">
          Free reports use the same engine as paid plans — no watered-down output.
        </p>

      </div>
    </div>
  )
}
