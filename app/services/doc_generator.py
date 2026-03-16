"""
Documentation generation service — orchestrates parsing + LLM.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.models.schemas import (
    ConfigType, DocStyle, OutputFormat,
    GenerateResponse, ParseResult,
)
from app.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts per doc style
# ---------------------------------------------------------------------------

SYSTEM_PROMPTS = {
    DocStyle.TECHNICAL: """You are a senior infrastructure engineer at DK InfraEdge, a consulting firm specializing in network automation, cloud infrastructure, and AI-powered operations.

Generate comprehensive technical documentation from the provided infrastructure configuration. Include:
- Architecture overview with component relationships
- Configuration details and parameters
- Network topology (if applicable)
- Dependencies and prerequisites
- Security considerations
- Operational notes (monitoring, scaling, backup)

Use professional Markdown formatting with proper headings, tables, and code blocks. Be precise and actionable.""",

    DocStyle.EXECUTIVE: """You are writing infrastructure documentation for C-level executives and non-technical stakeholders.

Generate a high-level summary that covers:
- What the infrastructure does (business value)
- Key components and their roles (no jargon)
- Risk and reliability posture
- Cost implications (if detectable)
- Compliance and security posture

Use clear, non-technical language. Use bullet points and tables for clarity. Keep it under 2 pages.""",

    DocStyle.RUNBOOK: """You are writing an operational runbook for on-call engineers.

Generate step-by-step procedures including:
- Service overview and architecture
- Health check procedures
- Common failure modes and troubleshooting
- Restart/recovery procedures
- Escalation contacts (placeholder)
- Monitoring and alerting thresholds

Use numbered steps, code blocks for commands, and warning callouts for dangerous operations.""",

    DocStyle.AUDIT: """You are preparing infrastructure documentation for a compliance audit.

Generate documentation covering:
- Complete inventory of all components
- Access control and authentication mechanisms
- Data flow and storage locations
- Encryption in transit and at rest
- Logging and audit trail capabilities
- Compliance-relevant configurations (ports, protocols, credentials management)
- Identified gaps or concerns

Use formal language. Include a findings table with severity ratings.""",

    DocStyle.ONBOARDING: """You are writing onboarding documentation for a new team member joining DK InfraEdge.

Generate a friendly but thorough guide covering:
- What this infrastructure is and why it exists
- How the pieces fit together (simple architecture overview)
- How to access and interact with each component
- Common tasks they'll need to perform
- Where to find more information
- Tips and gotchas

Use a conversational but professional tone. Include diagrams descriptions where helpful.""",
}


async def generate_documentation(
    parsed: ParseResult,
    doc_style: DocStyle,
    output_format: OutputFormat,
    context: Optional[str] = None,
    include_diagram: bool = False,
    include_security_review: bool = False,
) -> GenerateResponse:
    """Generate documentation from parsed config using LLM."""

    client = get_llm_client()
    system_prompt = SYSTEM_PROMPTS[doc_style]

    # Build user prompt
    user_parts = [
        f"## Config Type: {parsed.config_type.value}",
        f"## Summary: {parsed.summary}",
        f"## Components ({len(parsed.components)} found):",
    ]

    for comp in parsed.components:
        user_parts.append(f"- {comp}")

    if context:
        user_parts.append(f"\n## Additional Context:\n{context}")

    if include_diagram:
        user_parts.append("\n## Include a Mermaid architecture diagram showing component relationships.")

    if include_security_review:
        user_parts.append("\n## Include a security posture review section with findings and recommendations.")

    user_parts.append(f"\n## Raw Configuration:\n```\n{parsed.raw_content[:8000]}\n```")

    if output_format == OutputFormat.HTML:
        user_parts.append("\n## Output the documentation as clean HTML with inline CSS styling.")
    else:
        user_parts.append("\n## Output the documentation as clean Markdown.")

    user_prompt = "\n".join(user_parts)

    # Generate
    content, usage = await client.generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=4096,
        temperature=0.3,
    )

    # Extract title from first heading
    title = "Infrastructure Documentation"
    for line in content.splitlines():
        if line.startswith("# "):
            title = line.lstrip("# ").strip()
            break

    # Extract section headings
    sections = [
        line.lstrip("#").strip()
        for line in content.splitlines()
        if line.startswith("## ")
    ]

    warnings = parsed.warnings.copy()
    if len(parsed.raw_content) > 8000:
        warnings.append("Config truncated to 8000 chars for LLM context — large files may lose detail")

    return GenerateResponse(
        title=title,
        content=content,
        format=output_format,
        config_type=parsed.config_type,
        doc_style=doc_style,
        sections=sections,
        token_usage=usage,
        warnings=warnings,
    )
