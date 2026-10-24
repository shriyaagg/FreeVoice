import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

PAYPAL_CLIENT_ID = os.environ["PAYPAL_CLIENT_ID"]
PAYPAL_SECRET = os.environ["PAYPAL_SECRET"]
PAYPAL_BASE_URL = "https://api-m.sandbox.paypal.com"
PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID", "")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash")
MOCK_LLM = os.getenv("MOCK_LLM", "0") == "1"

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

with open(Path(__file__).parent / "policy.yaml") as f:
    POLICY = yaml.safe_load(f)