import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import config, db
from backend.api import analytics, calls, dashboard, demo
from backend.paypal import client, webhooks
from backend.scheduler import run_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    task = asyncio.create_task(run_scheduler())
    yield
    task.cancel()


app = FastAPI(title="PayPal collections agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_URL, "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(calls.router)
app.include_router(dashboard.router)
app.include_router(analytics.router)
app.include_router(demo.router)
app.include_router(webhooks.router)


@app.get("/health")
def health():
    return {"ok": True, "mock_llm": config.MOCK_LLM, "demo_mode": config.DEMO_MODE}


@app.get("/invoices")
def invoices():
    return [client.normalize(i) for i in client.list_invoices()]