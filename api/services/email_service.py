"""
Email alert service using Resend.
Sends score change alerts and other notifications to users.
"""

import os
from typing import List, Optional, Tuple
import resend

from api.services.alert_evaluator import AlertEvent

# Configure Resend API key
resend.api_key = os.getenv("RESEND_API_KEY", "")


async def send_score_change_alert(
    user_email: str,
    ticker: str,
    old_score: float,
    new_score: float,
    run_id: str
) -> Tuple[bool, str]:
    """
    Send email alert when watchlist score changes significantly.

    Args:
        user_email: Recipient email address
        ticker: Stock ticker symbol
        old_score: Previous moat score
        new_score: New moat score
        run_id: Analysis run ID for viewing report

    Returns:
        (success, error_message)
        - success: True if email sent successfully
        - error_message: Error description if failed, empty if success
    """
    if not resend.api_key:
        return False, "RESEND_API_KEY not configured"

    change = new_score - old_score
    direction = "increased" if change > 0 else "decreased"
    change_emoji = "📈" if change > 0 else "📉"

    subject = f"{change_emoji} {ticker} Score Alert: {abs(change):.1f} point change"

    # Base URL for report links (use environment variable or default)
    base_url = os.getenv("FRONTEND_URL", "https://dvrg.app")

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #00D9B5 0%, #00B396 100%);
            color: white;
            padding: 30px;
            border-radius: 10px 10px 0 0;
            text-align: center;
        }}
        .content {{
            background: white;
            padding: 30px;
            border: 1px solid #e0e0e0;
            border-top: none;
            border-radius: 0 0 10px 10px;
        }}
        .score-box {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .score-item {{
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            font-size: 16px;
        }}
        .score-label {{
            color: #666;
        }}
        .score-value {{
            font-weight: bold;
            color: #333;
        }}
        .change-positive {{
            color: #00D9B5;
        }}
        .change-negative {{
            color: #FF4D4D;
        }}
        .cta-button {{
            display: inline-block;
            background: #00D9B5;
            color: white;
            padding: 14px 28px;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 600;
            margin: 20px 0;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #999;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1 style="margin: 0; font-size: 24px;">🚨 Watchlist Alert</h1>
        <p style="margin: 10px 0 0 0; opacity: 0.9;">{ticker} Score Update</p>
    </div>

    <div class="content">
        <p>The DVRG Moat Score for <strong>{ticker}</strong> has {direction}:</p>

        <div class="score-box">
            <div class="score-item">
                <span class="score-label">Previous Score:</span>
                <span class="score-value">{old_score:.1f}/10</span>
            </div>
            <div class="score-item">
                <span class="score-label">New Score:</span>
                <span class="score-value">{new_score:.1f}/10</span>
            </div>
            <div class="score-item">
                <span class="score-label">Change:</span>
                <span class="score-value {'change-positive' if change > 0 else 'change-negative'}">
                    {change:+.1f} points
                </span>
            </div>
        </div>

        <p>This score change crossed your alert threshold. Review the full analysis to understand what changed.</p>

        <center>
            <a href="{base_url}/results/{run_id}" class="cta-button">
                View Full Analysis →
            </a>
        </center>

        <p style="margin-top: 30px; font-size: 14px; color: #666;">
            <strong>Tip:</strong> Check your watchlist dashboard to see score changes across all your tracked stocks.
        </p>
    </div>

    <div class="footer">
        <p>You're receiving this email because you have alerts enabled for {ticker} in your DVRG watchlist.</p>
        <p><a href="{base_url}/dashboard" style="color: #00D9B5;">Manage Alert Settings</a></p>
        <p style="margin-top: 20px;">
            Powered by <a href="https://dvrg.app" style="color: #00D9B5;">DVRG</a> •
            Stock Analysis with Signal Divergence Detection
        </p>
    </div>
</body>
</html>
"""

    try:
        response = resend.Emails.send({
            "from": "DVRG Alerts <alerts@dvrg.app>",
            "to": [user_email],
            "subject": subject,
            "html": html
        })

        print(f"✅ Alert email sent to {user_email} for {ticker}: {response}")
        return True, ""

    except Exception as e:
        error_msg = str(e)
        print(f"❌ Failed to send alert email to {user_email}: {error_msg}")
        return False, error_msg


async def send_weekly_digest(
    user_email: str,
    watchlist_summary: dict
) -> Tuple[bool, str]:
    """
    Send weekly digest of watchlist changes.

    Args:
        user_email: Recipient email address
        watchlist_summary: Dict with watchlist stats and top movers

    Returns:
        (success, error_message)
    """
    if not resend.api_key:
        return False, "RESEND_API_KEY not configured"

    # TODO: Implement weekly digest template
    # This will be built in Phase 2
    return False, "Weekly digest not yet implemented"


async def send_signal_alert(
    user_email: str,
    ticker: str,
    events: List[AlertEvent],
    run_id: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Send a single email summarising all weekly-batch alert events for one ticker.

    Args:
        user_email: Recipient.
        ticker: Stock ticker the events apply to.
        events: List of AlertEvent from alert_evaluator.evaluate_signal_change.
        run_id: Optional analysis run ID for the "View Full Analysis" link.

    Returns:
        (success, error_message)
    """
    if not resend.api_key:
        return False, "RESEND_API_KEY not configured"
    if not events:
        return False, "no events supplied"

    base_url = os.getenv("FRONTEND_URL", "https://dvrg.co")
    cta_path = f"/results/{run_id}" if run_id else f"/preview/{ticker.lower()}"

    def _render_event(e) -> str:
        if e.kind == "verdict_flip":
            return (
                f"<li><strong>Verdict flipped</strong>: "
                f"{str(e.prior_value).capitalize()} → "
                f"<span style='color:#00B396'>"
                f"{str(e.current_value).capitalize()}</span></li>"
            )
        if e.kind == "ev_change":
            prior_pct = int(round(float(e.prior_value) * 100))
            current_pct = int(round(float(e.current_value) * 100))
            direction = "↑" if current_pct > prior_pct else "↓"
            return (
                f"<li><strong>EV probability {direction}</strong>: "
                f"{prior_pct}% → {current_pct}%</li>"
            )
        # Unknown kind — render defensively rather than crash
        return f"<li>{e.kind}: {e.prior_value} → {e.current_value}</li>"

    event_list_html = "".join(_render_event(e) for e in events)
    kinds = {e.kind for e in events}
    if "verdict_flip" in kinds and "ev_change" in kinds:
        subject = f"🔔 {ticker}: Verdict flipped & EV probability moved"
    elif "verdict_flip" in kinds:
        subject = f"🔔 {ticker}: Verdict flipped"
    elif "ev_change" in kinds:
        subject = f"🔔 {ticker}: EV probability moved"
    else:
        subject = f"🔔 {ticker}: Weekly alert"

    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;
             max-width:600px;margin:0 auto;padding:24px;color:#333">
  <div style="background:linear-gradient(135deg,#00D9B5,#00B396);
              color:white;padding:24px;border-radius:8px 8px 0 0">
    <h1 style="margin:0;font-size:22px">Weekly Alert — {ticker}</h1>
    <p style="margin:6px 0 0;opacity:0.9">This week's batch moved a ticker on your watchlist.</p>
  </div>
  <div style="background:white;padding:24px;border:1px solid #e0e0e0;
              border-top:none;border-radius:0 0 8px 8px">
    <ul style="padding-left:20px;line-height:1.6">
      {event_list_html}
    </ul>
    <p style="margin-top:24px">
      <a href="{base_url}{cta_path}"
         style="display:inline-block;background:#00D9B5;color:white;
                padding:12px 22px;text-decoration:none;border-radius:6px;
                font-weight:600">View Full Analysis →</a>
    </p>
    <p style="margin-top:24px;font-size:12px;color:#999">
      You're receiving this because {ticker} is on your DVRG watchlist with
      alerts enabled.
      <a href="{base_url}/dashboard" style="color:#00D9B5">Manage alerts</a>
    </p>
  </div>
</body>
</html>
"""

    try:
        resend.Emails.send({
            "from": "DVRG Alerts <alerts@dvrg.co>",
            "to": [user_email],
            "subject": subject,
            "html": html,
        })
        return True, ""
    except Exception as e:
        return False, str(e)
