export const metadata = {
  title: 'Terms of Service - DVRG',
  description: 'DVRG Terms of Service — the rules and conditions for using our platform.',
}

const LAST_UPDATED = 'February 19, 2026'

export default function TermsOfServicePage() {
  return (
    <div className="container mx-auto px-4 py-16">
      <div className="max-w-3xl mx-auto space-y-10">

        <div className="space-y-3">
          <h1 className="text-4xl font-bold text-text-primary">Terms of Service</h1>
          <p className="text-sm text-text-tertiary">Last updated: {LAST_UPDATED}</p>
        </div>

        <p className="text-text-secondary leading-relaxed">
          Please read these Terms of Service (&quot;Terms&quot;) carefully before using DVRG
          (&quot;Service&quot;) operated by DVRG (&quot;us&quot;, &quot;we&quot;, &quot;our&quot;). By accessing or using the
          Service, you agree to be bound by these Terms.
        </p>

        <Section title="1. Use of the Service">
          <p className="text-text-secondary text-sm leading-relaxed">
            DVRG provides AI-powered financial data analysis tools for informational and
            educational purposes. You may use the Service only for lawful purposes and in
            accordance with these Terms. You agree not to:
          </p>
          <ul className="list-disc list-inside space-y-2 text-text-secondary text-sm leading-relaxed mt-3">
            <li>Use the Service to make investment decisions without independent verification</li>
            <li>Reverse engineer, scrape, or extract data from the platform in bulk</li>
            <li>Share account credentials or circumvent subscription limits</li>
            <li>Use the Service for any illegal purpose or in violation of any applicable law</li>
            <li>Interfere with or disrupt the integrity or performance of the Service</li>
          </ul>
        </Section>

        <Section title="2. Accounts">
          <p className="text-text-secondary text-sm leading-relaxed">
            You are responsible for maintaining the confidentiality of your account
            credentials and for all activity that occurs under your account. You must
            notify us immediately at{' '}
            <a href="mailto:support@dvrg.ai" className="text-primary hover:underline">
              support@dvrg.ai
            </a>{' '}
            of any unauthorized use of your account.
          </p>
        </Section>

        <Section title="3. Subscriptions and Billing">
          <p className="text-text-secondary text-sm leading-relaxed">
            Paid subscriptions are billed monthly in advance. Prices are subject to change
            with 30 days notice. Refunds are not provided for partial months. You may cancel
            your subscription at any time; access continues until the end of the current
            billing period. Payments are processed securely by Stripe.
          </p>
        </Section>

        <Section title="4. Not Financial Advice">
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-card p-4">
            <p className="text-sm text-amber-400 leading-relaxed font-medium">
              IMPORTANT: All content provided by DVRG is for informational and educational
              purposes only. Nothing on this platform constitutes financial, investment, legal,
              or tax advice. See our full{' '}
              <a href="/disclaimer" className="underline hover:text-amber-300">
                Investment Disclaimer
              </a>.
            </p>
          </div>
        </Section>

        <Section title="5. Intellectual Property">
          <p className="text-text-secondary text-sm leading-relaxed">
            The Service and its original content, features, and functionality are and will
            remain the exclusive property of DVRG. You may not reproduce, distribute, or
            create derivative works from any content without our express written permission.
            Analysis results generated from your queries are provided to you for personal use.
          </p>
        </Section>

        <Section title="6. Third-Party Data">
          <p className="text-text-secondary text-sm leading-relaxed">
            DVRG sources data from public and regulatory sources including SEC filings,
            FINRA, and market data providers. We do not guarantee the accuracy, completeness,
            or timeliness of this data. Market data is provided as-is and may contain errors
            or delays.
          </p>
        </Section>

        <Section title="7. Limitation of Liability">
          <p className="text-text-secondary text-sm leading-relaxed">
            To the maximum extent permitted by applicable law, DVRG shall not be liable for
            any indirect, incidental, special, consequential, or punitive damages, including
            loss of profits or data, arising from your use of the Service. Our total liability
            to you shall not exceed the amount paid by you in the 12 months preceding the claim.
          </p>
        </Section>

        <Section title="8. Disclaimer of Warranties">
          <p className="text-text-secondary text-sm leading-relaxed">
            The Service is provided &quot;as is&quot; and &quot;as available&quot; without warranties of any kind,
            either express or implied, including but not limited to warranties of merchantability,
            fitness for a particular purpose, or non-infringement.
          </p>
        </Section>

        <Section title="9. Termination">
          <p className="text-text-secondary text-sm leading-relaxed">
            We may terminate or suspend your account and access to the Service at our sole
            discretion, without notice, for conduct that we believe violates these Terms or
            is harmful to other users, us, or third parties.
          </p>
        </Section>

        <Section title="10. Governing Law">
          <p className="text-text-secondary text-sm leading-relaxed">
            These Terms shall be governed by the laws of the United States, without regard
            to its conflict of law provisions. Any disputes arising under these Terms shall
            be resolved through binding arbitration.
          </p>
        </Section>

        <Section title="11. Changes to Terms">
          <p className="text-text-secondary text-sm leading-relaxed">
            We reserve the right to modify these Terms at any time. We will provide notice
            of material changes. Your continued use of the Service after changes constitutes
            your acceptance of the revised Terms.
          </p>
        </Section>

        <Section title="12. Contact">
          <p className="text-text-secondary text-sm leading-relaxed">
            Questions about these Terms? Contact us at{' '}
            <a href="mailto:support@dvrg.ai" className="text-primary hover:underline">
              support@dvrg.ai
            </a>.
          </p>
        </Section>

      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-4 pt-4 border-t border-surface-elevated">
      <h2 className="text-lg font-semibold text-text-primary">{title}</h2>
      {children}
    </div>
  )
}
