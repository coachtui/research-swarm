"""
Inngest function registry and HTTP handler.

This file exposes all Inngest functions and provides
the HTTP endpoint for Inngest Cloud to invoke them.
"""

from inngest import Inngest
from inngest.flask import serve
from flask import Flask
import os

# Import all function modules
from inngest.functions.analyze_stock import inngest, analyze_stock
from inngest.functions.weekly_batch import weekly_batch
from inngest.functions.send_teaser_digest import send_teaser_digest
from inngest.functions.send_watchlist_alerts import send_watchlist_alerts

# Create Flask app for Inngest HTTP handler
app = Flask(__name__)

# Register Inngest functions with Flask
serve(
    app,
    inngest,
    [analyze_stock, weekly_batch, send_teaser_digest, send_watchlist_alerts],
    signing_key=os.getenv("INNGEST_SIGNING_KEY")
)

if __name__ == "__main__":
    # For local development
    app.run(host="0.0.0.0", port=8001, debug=True)
