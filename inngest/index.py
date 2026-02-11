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

# Create Flask app for Inngest HTTP handler
app = Flask(__name__)

# Register Inngest functions with Flask
serve(
    app,
    inngest,
    [analyze_stock],
    signing_key=os.getenv("INNGEST_SIGNING_KEY")
)

if __name__ == "__main__":
    # For local development
    app.run(host="0.0.0.0", port=8001, debug=True)
