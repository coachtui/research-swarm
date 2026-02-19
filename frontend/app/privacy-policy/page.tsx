export const metadata = {
  title: 'Privacy Policy - DVRG',
  description: 'DVRG Privacy Policy — how we collect, use, and protect your data.',
}

const LAST_UPDATED = 'February 19, 2026'

export default function PrivacyPolicyPage() {
  return (
    <div className="container mx-auto px-4 py-16">
      <div className="max-w-3xl mx-auto space-y-10">

        <div className="space-y-3">
          <h1 className="text-4xl font-bold text-text-primary">Privacy Policy</h1>
          <p className="text-sm text-text-tertiary">Last updated: {LAST_UPDATED}</p>
        </div>

        <p className="text-text-secondary leading-relaxed">
          DVRG (&quot;we&quot;, &quot;our&quot;, or &quot;us&quot;) is committed to protecting your privacy.
          This Privacy Policy explains how we collect, use, disclose, and safeguard your information
          when you use our platform at dvrg.ai (the &quot;Service&quot;).
        </p>

        <Section title="1. Information We Collect">
          <SubSection title="Account Information">
            When you create an account, we collect your email address and name via our
            authentication provider (Clerk). We do not store your password — authentication
            is handled entirely by Clerk.
          </SubSection>
          <SubSection title="Usage Data">
            We collect information about how you use the Service, including stock tickers
            you analyze, analysis history, and feature interactions. This data is used to
            improve the Service and personalize your experience.
          </SubSection>
          <SubSection title="Payment Information">
            Payments are processed by Stripe. We do not store credit card numbers or full
            payment details. We receive a subscription status and customer ID from Stripe
            to manage your plan.
          </SubSection>
          <SubSection title="Log Data">
            Our servers automatically record information including your IP address, browser
            type, pages visited, and timestamps when you access the Service.
          </SubSection>
        </Section>

        <Section title="2. How We Use Your Information">
          <ul className="list-disc list-inside space-y-2 text-text-secondary text-sm leading-relaxed">
            <li>To provide, operate, and maintain the Service</li>
            <li>To process transactions and manage your subscription</li>
            <li>To send transactional emails (account confirmations, billing receipts)</li>
            <li>To monitor usage and improve platform performance</li>
            <li>To detect and prevent fraud or abuse</li>
            <li>To comply with legal obligations</li>
          </ul>
        </Section>

        <Section title="3. Sharing of Information">
          <p className="text-text-secondary text-sm leading-relaxed">
            We do not sell, trade, or rent your personal information to third parties.
            We share data only with:
          </p>
          <ul className="list-disc list-inside space-y-2 text-text-secondary text-sm leading-relaxed mt-3">
            <li><strong className="text-text-primary">Clerk</strong> — identity and authentication management</li>
            <li><strong className="text-text-primary">Stripe</strong> — payment processing and subscription billing</li>
            <li><strong className="text-text-primary">Hosting providers</strong> — infrastructure necessary to run the Service</li>
            <li><strong className="text-text-primary">Law enforcement</strong> — when required by applicable law</li>
          </ul>
        </Section>

        <Section title="4. Data Retention">
          <p className="text-text-secondary text-sm leading-relaxed">
            We retain your account data for as long as your account is active. Analysis
            results are stored to provide your history and are retained for up to 12 months.
            You may request deletion of your data at any time by contacting us.
          </p>
        </Section>

        <Section title="5. Cookies">
          <p className="text-text-secondary text-sm leading-relaxed">
            We use strictly necessary cookies for authentication session management.
            We do not use third-party advertising cookies or tracking pixels.
          </p>
        </Section>

        <Section title="6. Security">
          <p className="text-text-secondary text-sm leading-relaxed">
            We implement industry-standard security measures including HTTPS encryption,
            secure token handling, and access controls. No method of transmission over the
            internet is 100% secure, and we cannot guarantee absolute security.
          </p>
        </Section>

        <Section title="7. Your Rights">
          <p className="text-text-secondary text-sm leading-relaxed">
            Depending on your jurisdiction, you may have the right to access, correct, or
            delete personal data we hold about you. To exercise these rights, contact us at{' '}
            <a href="mailto:support@dvrg.ai" className="text-primary hover:underline">
              support@dvrg.ai
            </a>.
          </p>
        </Section>

        <Section title="8. Children's Privacy">
          <p className="text-text-secondary text-sm leading-relaxed">
            The Service is not directed to individuals under 18. We do not knowingly collect
            personal information from children.
          </p>
        </Section>

        <Section title="9. Changes to This Policy">
          <p className="text-text-secondary text-sm leading-relaxed">
            We may update this Privacy Policy from time to time. We will notify you of
            material changes by posting the new policy with an updated &quot;Last updated&quot; date.
            Your continued use of the Service after changes constitutes acceptance.
          </p>
        </Section>

        <Section title="10. Contact">
          <p className="text-text-secondary text-sm leading-relaxed">
            For privacy-related questions, contact us at{' '}
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

function SubSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <h3 className="text-sm font-medium text-text-primary">{title}</h3>
      <p className="text-text-secondary text-sm leading-relaxed">{children}</p>
    </div>
  )
}
