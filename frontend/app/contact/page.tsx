export const metadata = {
  title: 'Contact - DVRG',
  description: 'Get in touch with the DVRG team for support, partnerships, or feedback.',
}

export default function ContactPage() {
  return (
    <div className="container mx-auto px-4 py-16">
      <div className="max-w-2xl mx-auto space-y-12">

        {/* Header */}
        <div className="space-y-3">
          <h1 className="text-4xl font-bold text-text-primary">Contact</h1>
          <p className="text-lg text-text-secondary">
            Have a question, found a bug, or want to partner with us? We&apos;d love to hear from you.
          </p>
        </div>

        {/* Contact options */}
        <div className="grid gap-6 md:grid-cols-2">
          <div className="bg-surface rounded-card p-6 space-y-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <svg className="h-5 w-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
              </svg>
            </div>
            <h3 className="font-semibold text-text-primary">General & Support</h3>
            <p className="text-sm text-text-secondary">
              Questions about the platform, billing, or your account.
            </p>
            <a
              href="mailto:support.dvrg.io@aigaai.com"
              className="text-sm text-primary hover:underline"
            >
              support.dvrg.io@aigaai.com
            </a>
          </div>

          <div className="bg-surface rounded-card p-6 space-y-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <svg className="h-5 w-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M13.5 21v-7.5a.75.75 0 01.75-.75h3a.75.75 0 01.75.75V21m-4.5 0H2.36m11.14 0H18m0 0h3.64m-1.39 0V9.349m-16.5 11.65V9.35m0 0a3.001 3.001 0 003.75-.615A2.993 2.993 0 009.75 9.75c.896 0 1.7-.393 2.25-1.016a2.993 2.993 0 002.25 1.016c.896 0 1.7-.393 2.25-1.016a3.001 3.001 0 003.75.614m-16.5 0a3.004 3.004 0 01-.621-4.72L4.318 3.44A1.5 1.5 0 015.378 3h13.243a1.5 1.5 0 011.06.44l1.19 1.189a3 3 0 01-.621 4.72m-13.5 8.65h3.75a.75.75 0 00.75-.75V13.5a.75.75 0 00-.75-.75H6.75a.75.75 0 00-.75.75v3.75c0 .415.336.75.75.75z" />
              </svg>
            </div>
            <h3 className="font-semibold text-text-primary">Partnerships & Business</h3>
            <p className="text-sm text-text-secondary">
              API integrations, institutional licensing, or press inquiries.
            </p>
            <a
              href="mailto:hello.dvrg.io@aigaai.com"
              className="text-sm text-primary hover:underline"
            >
              hello.dvrg.io@aigaai.com
            </a>
          </div>
        </div>

        {/* Response time note */}
        <div className="bg-surface/50 border border-surface-elevated rounded-card p-5 flex gap-4">
          <svg className="h-5 w-5 text-text-tertiary flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-sm text-text-secondary">
            We typically respond within 1–2 business days. For urgent account issues,
            please include your registered email address in your message.
          </p>
        </div>

      </div>
    </div>
  )
}
