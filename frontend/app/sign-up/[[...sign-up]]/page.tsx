import { SignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  return (
    <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center py-12 px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-text-primary mb-2">Get Started Free</h1>
          <p className="text-text-secondary">
            Create your account and get your first analysis free
          </p>
        </div>
        <SignUp
          appearance={{
            variables: {
              colorPrimary: "#06b6d4",
              colorTextOnPrimaryBackground: "#ffffff",
              colorText: "#e5e7eb",
              colorTextSecondary: "#9ca3af",
              colorBackground: "#1f2937",
              colorInputBackground: "#374151",
              colorInputText: "#f3f4f6",
            },
            elements: {
              rootBox: "mx-auto",
              card: "bg-surface border border-surface-elevated shadow-xl",
              headerTitle: "text-text-primary",
              headerSubtitle: "text-text-secondary",
              socialButtonsBlockButton: "bg-surface-elevated border border-surface-elevated text-text-primary hover:bg-surface",
              formButtonPrimary: "bg-primary hover:bg-primary-dark text-white",
              formButtonReset: "text-primary hover:text-primary-dark",
              formFieldInput: "bg-surface-elevated border-surface-elevated text-text-primary",
              formFieldLabel: "text-text-primary font-medium",
              formFieldLabelRow: "text-text-primary",
              formFieldInputShowPasswordButton: "text-text-secondary hover:text-text-primary",
              formFieldAction: "text-primary hover:text-primary-dark",
              formFieldHintText: "text-text-secondary",
              formResendCodeLink: "text-primary hover:text-primary-dark",
              identityPreviewText: "text-text-primary",
              identityPreviewEditButton: "text-primary hover:text-primary-dark",
              alternativeMethodsBlockButton: "text-primary hover:text-primary-dark border border-surface-elevated",
              alternativeMethodsBlockButtonText: "text-primary",
              formHeaderTitle: "text-text-primary",
              formHeaderSubtitle: "text-text-secondary",
              otpCodeFieldInput: "text-text-primary border-surface-elevated",
              dividerLine: "bg-surface-elevated",
              dividerText: "text-text-secondary",
              footerActionLink: "text-primary hover:text-primary-dark font-semibold",
              footerActionText: "text-text-secondary",
              footerAction: "text-text-secondary",
              optionalFieldText: "text-text-tertiary text-xs",
            },
          }}
        />
      </div>
    </div>
  );
}
