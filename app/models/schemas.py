"""Pydantic models for DocGen API."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ConfigType(str, Enum):
    """Supported infrastructure config types."""
    ANSIBLE_PLAYBOOK = "ansible_playbook"
    ANSIBLE_INVENTORY = "ansible_inventory"
    TERRAFORM = "terraform"
    KUBERNETES = "kubernetes"
    DOCKER_COMPOSE = "docker_compose"
    NETWORK_CONFIG = "network_config"       # Cisco IOS, JunOS, etc.
    NGINX = "nginx"
    SYSTEMD = "systemd"
    SYSLOG = "syslog"
    APPLICATION_LOG = "application_log"
    GENERIC = "generic"
    AUTO_DETECT = "auto_detect"


class OutputFormat(str, Enum):
    """Output documentation format."""
    MARKDOWN = "markdown"
    HTML = "html"


class DocStyle(str, Enum):
    """Documentation style/audience."""
    TECHNICAL = "technical"          # For engineers
    EXECUTIVE = "executive"          # For leadership
    RUNBOOK = "runbook"              # Operational procedures
    AUDIT = "audit"                  # Compliance/audit trail
    ONBOARDING = "onboarding"        # New team member guide


class GenerateRequest(BaseModel):
    """Request to generate documentation from uploaded content."""
    raw_config: str = Field(..., description="Raw infrastructure config text")
    config_type: ConfigType = ConfigType.AUTO_DETECT
    output_format: OutputFormat = OutputFormat.MARKDOWN
    doc_style: DocStyle = DocStyle.TECHNICAL
    context: Optional[str] = Field(
        None,
        description="Additional context about the infrastructure (environment, purpose, constraints)",
    )
    include_diagram: bool = Field(
        False,
        description="Include a Mermaid architecture diagram",
    )
    include_security_review: bool = Field(
        False,
        description="Include security posture analysis",
    )


class GenerateResponse(BaseModel):
    """Generated documentation response."""
    title: str
    content: str
    format: OutputFormat
    config_type: ConfigType
    doc_style: DocStyle
    sections: list[str]
    token_usage: dict
    warnings: list[str] = []


class ParseResult(BaseModel):
    """Result from config parser."""
    config_type: ConfigType
    summary: str
    components: list[dict]
    raw_content: str
    file_count: int
    warnings: list[str] = []
