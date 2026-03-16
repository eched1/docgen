"""
Document generation API endpoints.

POST /api/v1/generate         — Upload file(s) + options → get documentation
POST /api/v1/generate/text    — Paste raw config text → get documentation
GET  /api/v1/formats          — List supported config types and doc styles
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile, HTTPException

from app.models.schemas import (
    ConfigType, DocStyle, OutputFormat,
    GenerateRequest, GenerateResponse,
)
from app.parsers.config_parser import parse_config, detect_config_type
from app.services.doc_generator import generate_documentation

logger = logging.getLogger(__name__)
router = APIRouter(tags=["documents"])


@router.post("/generate", response_model=GenerateResponse)
async def generate_from_file(
    file: UploadFile = File(..., description="Infrastructure config or log file"),
    config_type: ConfigType = Form(ConfigType.AUTO_DETECT),
    output_format: OutputFormat = Form(OutputFormat.MARKDOWN),
    doc_style: DocStyle = Form(DocStyle.TECHNICAL),
    context: Optional[str] = Form(None),
    include_diagram: bool = Form(False),
    include_security_review: bool = Form(False),
):
    """Upload an infrastructure config file and generate documentation."""
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "File must be UTF-8 text (not binary)")

    if len(text.strip()) == 0:
        raise HTTPException(400, "Uploaded file is empty")

    if len(text) > 100_000:
        raise HTTPException(413, "File too large — max 100KB for MVP")

    parsed = parse_config(text, config_type, filename=file.filename or "")

    return await generate_documentation(
        parsed=parsed,
        doc_style=doc_style,
        output_format=output_format,
        context=context,
        include_diagram=include_diagram,
        include_security_review=include_security_review,
    )


@router.post("/generate/text", response_model=GenerateResponse)
async def generate_from_text(request: GenerateRequest, raw_config: str = ""):
    """Paste raw config text and generate documentation."""
    # Accept raw_config from body or use a combined model
    if not raw_config:
        raise HTTPException(400, "raw_config field is required")

    if len(raw_config) > 100_000:
        raise HTTPException(413, "Config too large — max 100KB for MVP")

    parsed = parse_config(raw_config, request.config_type)

    return await generate_documentation(
        parsed=parsed,
        doc_style=request.doc_style,
        output_format=request.output_format,
        context=request.context,
        include_diagram=request.include_diagram,
        include_security_review=request.include_security_review,
    )


@router.post("/generate/batch", response_model=list[GenerateResponse])
async def generate_batch(
    files: list[UploadFile] = File(..., description="Multiple config files"),
    config_type: ConfigType = Form(ConfigType.AUTO_DETECT),
    output_format: OutputFormat = Form(OutputFormat.MARKDOWN),
    doc_style: DocStyle = Form(DocStyle.TECHNICAL),
    context: Optional[str] = Form(None),
):
    """Upload multiple files and generate a combined documentation set."""
    results = []
    for file in files:
        content = await file.read()
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            continue

        if not text.strip():
            continue

        parsed = parse_config(text, config_type, filename=file.filename or "")
        result = await generate_documentation(
            parsed=parsed,
            doc_style=doc_style,
            output_format=output_format,
            context=context,
        )
        results.append(result)

    if not results:
        raise HTTPException(400, "No valid files to process")

    return results


@router.get("/formats")
async def list_formats():
    """List all supported config types, doc styles, and output formats."""
    return {
        "config_types": [{"value": ct.value, "name": ct.name} for ct in ConfigType],
        "doc_styles": [{"value": ds.value, "name": ds.name} for ds in DocStyle],
        "output_formats": [{"value": of.value, "name": of.name} for of in OutputFormat],
    }
