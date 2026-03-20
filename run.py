"""
run.py — Application entry point
Starts the Flask server with WebSocket support via flask-sock
"""

import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    print(f"Resume Analyzer API starting on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
