"""Email notification system with SMTP and SendGrid support."""

import smtplib
from abc import ABC, abstractmethod
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional

from jinja2 import Environment, PackageLoader

from research_swarm.automation.models import (
    AutomationResult,
    CostReport,
    EmailConfig,
    EmailProvider,
    NotificationConfig,
    NotificationResult,
)
from research_swarm.logger import logger


class EmailSender(ABC):
    """Abstract base class for email providers."""

    @abstractmethod
    def send(
        self,
        to: List[str],
        subject: str,
        body_html: str,
        body_text: str,
        attachments: Optional[List[Path]] = None,
    ) -> NotificationResult:
        """Send an email."""
        pass


class SMTPSender(EmailSender):
    """SMTP email sender."""

    def __init__(self, config: EmailConfig):
        self.config = config

    def send(
        self,
        to: List[str],
        subject: str,
        body_html: str,
        body_text: str,
        attachments: Optional[List[Path]] = None,
    ) -> NotificationResult:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.config.from_name} <{self.config.from_email}>"
            msg["To"] = ", ".join(to)

            msg.attach(MIMEText(body_text, "plain"))
            msg.attach(MIMEText(body_html, "html"))

            # Add attachments
            if attachments:
                for file_path in attachments:
                    if file_path.exists():
                        with open(file_path, "rb") as f:
                            part = MIMEApplication(f.read(), Name=file_path.name)
                            part["Content-Disposition"] = (
                                f'attachment; filename="{file_path.name}"'
                            )
                            msg.attach(part)

            # Send via SMTP
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                if self.config.smtp_use_tls:
                    server.starttls()
                if self.config.smtp_user and self.config.smtp_password:
                    server.login(self.config.smtp_user, self.config.smtp_password)
                server.sendmail(self.config.from_email, to, msg.as_string())

            return NotificationResult(success=True, recipients_sent=to)

        except Exception as e:
            logger.error(f"SMTP send failed: {e}")
            return NotificationResult(
                success=False,
                recipients_failed=to,
                error_message=str(e),
            )


class SendGridSender(EmailSender):
    """SendGrid email sender."""

    def __init__(self, config: EmailConfig):
        self.config = config

    def send(
        self,
        to: List[str],
        subject: str,
        body_html: str,
        body_text: str,
        attachments: Optional[List[Path]] = None,
    ) -> NotificationResult:
        try:
            import base64

            import sendgrid
            from sendgrid.helpers.mail import (
                Attachment,
                Content,
                Email,
                FileContent,
                FileName,
                FileType,
                Mail,
                To,
            )

            sg = sendgrid.SendGridAPIClient(api_key=self.config.sendgrid_api_key)

            message = Mail(
                from_email=Email(self.config.from_email, self.config.from_name),
                to_emails=[To(email) for email in to],
                subject=subject,
            )
            message.add_content(Content("text/plain", body_text))
            message.add_content(Content("text/html", body_html))

            # Add attachments
            if attachments:
                for file_path in attachments:
                    if file_path.exists():
                        with open(file_path, "rb") as f:
                            data = base64.b64encode(f.read()).decode()

                        attachment = Attachment()
                        attachment.file_content = FileContent(data)
                        attachment.file_name = FileName(file_path.name)
                        attachment.file_type = FileType("application/pdf")
                        message.add_attachment(attachment)

            response = sg.send(message)

            if response.status_code in (200, 201, 202):
                return NotificationResult(success=True, recipients_sent=to)
            else:
                return NotificationResult(
                    success=False,
                    recipients_failed=to,
                    error_message=f"SendGrid returned {response.status_code}",
                )

        except Exception as e:
            logger.error(f"SendGrid send failed: {e}")
            return NotificationResult(
                success=False,
                recipients_failed=to,
                error_message=str(e),
            )


class Notifier:
    """Email notification manager."""

    def __init__(
        self,
        email_config: EmailConfig,
        notification_config: NotificationConfig,
    ):
        self.email_config = email_config
        self.notification_config = notification_config
        self.sender = self._create_sender()
        self.templates = Environment(
            loader=PackageLoader("research_swarm.automation", "templates"),
            autoescape=True,
        )

    def _create_sender(self) -> EmailSender:
        """Factory method to create appropriate email sender."""
        if self.email_config.provider == EmailProvider.SENDGRID:
            return SendGridSender(self.email_config)
        return SMTPSender(self.email_config)

    def send_run_completion(
        self,
        result: AutomationResult,
        pdf_path: Optional[Path] = None,
    ) -> NotificationResult:
        """Send run completion notification with optional PDF attachment."""
        if not self.notification_config.send_on_completion:
            return NotificationResult(success=True, recipients_sent=[])

        template = self.templates.get_template("email_report.html.j2")
        body_html = template.render(result=result)

        body_text = f"""
Research Swarm Analysis Complete

Run ID: {result.run_id}
Stocks Analyzed: {result.tickers_analyzed}
Completed: {result.completed_count}
Failed: {result.failed_count}
Cost: ${result.cost_usd:.2f}

Watchlist Candidates: {', '.join(result.watchlist_candidates) or 'None'}
High Priority (>=9): {', '.join(result.high_priority_stocks) or 'None'}
        """.strip()

        subject = f"[Research Swarm] Analysis Complete - {result.completed_count}/{result.tickers_analyzed} stocks"

        if result.high_priority_stocks:
            subject = f"[HIGH PRIORITY] {subject}"

        attachments = []
        if (
            pdf_path
            and pdf_path.exists()
            and self.notification_config.attach_pdf_report
        ):
            attachments.append(pdf_path)

        return self.sender.send(
            to=self.email_config.recipients,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            attachments=attachments,
        )

    def send_error_notification(
        self,
        error_message: str,
        run_id: Optional[str] = None,
    ) -> NotificationResult:
        """Send error notification."""
        if not self.notification_config.send_on_error:
            return NotificationResult(success=True, recipients_sent=[])

        subject = "[Research Swarm ERROR] Run failed"
        if run_id:
            subject += f" - {run_id}"

        body_text = f"""
Research Swarm encountered an error.

Run ID: {run_id or 'N/A'}
Error: {error_message}

Please check the logs for more details.
        """.strip()

        body_html = (
            f"<h2>Research Swarm Error</h2>"
            f"<p><strong>Error:</strong> {error_message}</p>"
        )

        return self.sender.send(
            to=self.email_config.recipients,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
        )

    def send_budget_alert(self, cost_report: CostReport) -> NotificationResult:
        """Send budget warning notification."""
        subject = (
            f"[Research Swarm ALERT] Budget threshold exceeded - "
            f"${cost_report.total_cost_usd:.2f}"
        )

        body_text = f"""
Budget Alert!

Month: {cost_report.month}
Current Spend: ${cost_report.total_cost_usd:.2f}
Budget Remaining: ${cost_report.budget_remaining_usd:.2f}

Consider reducing analysis frequency or stock count.
        """.strip()

        body_html = f"""
<h2>Budget Alert</h2>
<p><strong>Month:</strong> {cost_report.month}</p>
<p><strong>Current Spend:</strong> ${cost_report.total_cost_usd:.2f}</p>
<p><strong>Budget Remaining:</strong> ${cost_report.budget_remaining_usd:.2f}</p>
        """

        return self.sender.send(
            to=self.email_config.recipients,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
        )

    def send_test(self) -> NotificationResult:
        """Send a test notification."""
        return self.sender.send(
            to=self.email_config.recipients,
            subject="[Research Swarm] Test Notification",
            body_html=(
                "<h2>Test Email</h2>"
                "<p>This is a test email from Research Swarm.</p>"
            ),
            body_text="Test email from Research Swarm.",
        )
