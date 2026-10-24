from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import config, db
from backend.api import calls, dashboard
from backend.paypal import client, webhooks


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="PayPal collections agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_URL, "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(calls.router)
app.include_router(dashboard.router)
app.include_router(webhooks.router)


@app.get("/health")
def health():
    return {"ok": True, "mock_llm": config.MOCK_LLM}


@app.get("/invoices")
def invoices():
    return [client.normalize(i) for i in client.list_invoices()]