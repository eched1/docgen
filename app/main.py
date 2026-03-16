"""
DK InfraEdge — Automated Documentation Generator
MVP: Upload infrastructure configs/logs → AI-generated professional documentation.

Supports: Ansible, Terraform, Kubernetes YAML, Docker Compose, network configs,
           syslog, application logs, and generic text files.
"""

from __future__ import annotations

import os
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import documents, health
from app.services.llm_client import get_llm_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DK InfraEdge DocGen",
    description="Automated infrastructure documentation generator",
    version="0.1.0",
)

# CORS
cors_origins = os.getenv("CORS_ORIGINS", "https://logsight.home.arpa,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router)
app.include_router(documents.router, prefix="/api/v1")


@app.on_event("startup")
async def startup():
    """Validate LLM client configuration on startup."""
    client = get_llm_client()
    logger.info(f"DocGen MVP started — LLM provider: {client.provider}")
