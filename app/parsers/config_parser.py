"""
Infrastructure config parser — detects type and extracts structured components.

Supports: Ansible, Terraform, Kubernetes, Docker Compose, network configs,
           Nginx, systemd units, syslog, application logs.
"""

from __future__ import annotations

import re
import logging
from typing import Any

import yaml
import json

from app.models.schemas import ConfigType, ParseResult

logger = logging.getLogger(__name__)


def detect_config_type(content: str, filename: str = "") -> ConfigType:
    """Auto-detect infrastructure config type from content and filename."""
    fname = filename.lower()

    # Filename-based detection
    if fname.endswith((".tf", ".tfvars")):
        return ConfigType.TERRAFORM
    if fname in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
        return ConfigType.DOCKER_COMPOSE
    if fname.endswith(".service") or fname.endswith(".timer"):
        return ConfigType.SYSTEMD
    if "inventory" in fname and (fname.endswith(".yml") or fname.endswith(".yaml") or fname.endswith(".ini")):
        return ConfigType.ANSIBLE_INVENTORY
    if fname.endswith((".yml", ".yaml")) and ("playbook" in fname or "site" in fname or "main" in fname):
        return ConfigType.ANSIBLE_PLAYBOOK

    # Content-based detection
    if _is_terraform(content):
        return ConfigType.TERRAFORM
    if _is_kubernetes(content):
        return ConfigType.KUBERNETES
    if _is_docker_compose(content):
        return ConfigType.DOCKER_COMPOSE
    if _is_ansible_playbook(content):
        return ConfigType.ANSIBLE_PLAYBOOK
    if _is_nginx(content):
        return ConfigType.NGINX
    if _is_network_config(content):
        return ConfigType.NETWORK_CONFIG
    if _is_syslog(content):
        return ConfigType.SYSLOG
    if _is_systemd(content):
        return ConfigType.SYSTEMD

    return ConfigType.GENERIC


def parse_config(content: str, config_type: ConfigType, filename: str = "") -> ParseResult:
    """Parse infrastructure config and extract structured components."""
    if config_type == ConfigType.AUTO_DETECT:
        config_type = detect_config_type(content, filename)

    components: list[dict] = []
    warnings: list[str] = []
    summary = ""

    try:
        if config_type == ConfigType.KUBERNETES:
            components, summary = _parse_kubernetes(content)
        elif config_type == ConfigType.ANSIBLE_PLAYBOOK:
            components, summary = _parse_ansible(content)
        elif config_type == ConfigType.TERRAFORM:
            components, summary = _parse_terraform(content)
        elif config_type == ConfigType.DOCKER_COMPOSE:
            components, summary = _parse_docker_compose(content)
        elif config_type == ConfigType.NGINX:
            components, summary = _parse_nginx(content)
        elif config_type in (ConfigType.SYSLOG, ConfigType.APPLICATION_LOG):
            components, summary = _parse_logs(content)
        elif config_type == ConfigType.NETWORK_CONFIG:
            components, summary = _parse_network_config(content)
        else:
            summary = f"Generic config file ({len(content.splitlines())} lines)"
            components = [{"type": "raw", "content": content[:2000]}]
    except Exception as e:
        logger.warning(f"Parse error for {config_type}: {e}")
        warnings.append(f"Partial parse: {e}")
        summary = f"Failed to fully parse as {config_type.value}"
        components = [{"type": "raw", "content": content[:2000]}]

    return ParseResult(
        config_type=config_type,
        summary=summary,
        components=components,
        raw_content=content,
        file_count=1,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def _is_terraform(content: str) -> bool:
    return bool(re.search(r'(resource|provider|variable|output|data)\s+"', content))


def _is_kubernetes(content: str) -> bool:
    return "apiVersion:" in content and "kind:" in content


def _is_docker_compose(content: str) -> bool:
    return "services:" in content and ("image:" in content or "build:" in content)


def _is_ansible_playbook(content: str) -> bool:
    return bool(re.search(r"(hosts:|tasks:|roles:|handlers:)", content))


def _is_nginx(content: str) -> bool:
    return bool(re.search(r"(server\s*\{|upstream\s+|location\s+)", content))


def _is_network_config(content: str) -> bool:
    return bool(re.search(r"(interface\s+(Ethernet|GigabitEthernet|Vlan|Loopback)|router\s+(ospf|bgp|eigrp))", content, re.IGNORECASE))


def _is_syslog(content: str) -> bool:
    return bool(re.search(r"^<?\d+>?\s*\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}", content, re.MULTILINE))


def _is_systemd(content: str) -> bool:
    return "[Unit]" in content or "[Service]" in content


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _parse_kubernetes(content: str) -> tuple[list[dict], str]:
    docs = list(yaml.safe_load_all(content))
    components = []
    kinds: dict[str, int] = {}
    for doc in docs:
        if not doc or not isinstance(doc, dict):
            continue
        kind = doc.get("kind", "Unknown")
        name = doc.get("metadata", {}).get("name", "unnamed")
        namespace = doc.get("metadata", {}).get("namespace", "default")
        kinds[kind] = kinds.get(kind, 0) + 1
        comp = {
            "type": "k8s_resource",
            "kind": kind,
            "name": name,
            "namespace": namespace,
            "api_version": doc.get("apiVersion", ""),
        }
        # Extract key details per kind
        if kind == "Deployment":
            spec = doc.get("spec", {})
            comp["replicas"] = spec.get("replicas", 1)
            containers = spec.get("template", {}).get("spec", {}).get("containers", [])
            comp["containers"] = [
                {"name": c.get("name"), "image": c.get("image"), "ports": c.get("ports", [])}
                for c in containers
            ]
        elif kind == "Service":
            spec = doc.get("spec", {})
            comp["service_type"] = spec.get("type", "ClusterIP")
            comp["ports"] = spec.get("ports", [])
        elif kind == "Ingress":
            spec = doc.get("spec", {})
            comp["rules"] = spec.get("rules", [])
        components.append(comp)

    summary_parts = [f"{count}x {kind}" for kind, count in sorted(kinds.items())]
    summary = f"Kubernetes manifest: {', '.join(summary_parts)}" if summary_parts else "Empty Kubernetes manifest"
    return components, summary


def _parse_ansible(content: str) -> tuple[list[dict], str]:
    data = yaml.safe_load(content)
    if not isinstance(data, list):
        data = [data]
    components = []
    for play in data:
        if not isinstance(play, dict):
            continue
        comp = {
            "type": "ansible_play",
            "name": play.get("name", "unnamed"),
            "hosts": play.get("hosts", "all"),
            "tasks": [],
            "roles": play.get("roles", []),
            "vars": list(play.get("vars", {}).keys()) if isinstance(play.get("vars"), dict) else [],
        }
        for task in play.get("tasks", []):
            if isinstance(task, dict):
                module = next((k for k in task if k not in ("name", "register", "when", "become", "tags", "notify", "vars", "loop", "with_items")), "unknown")
                comp["tasks"].append({
                    "name": task.get("name", "unnamed"),
                    "module": module,
                })
        components.append(comp)
    task_count = sum(len(c["tasks"]) for c in components)
    summary = f"Ansible playbook: {len(components)} play(s), {task_count} task(s)"
    return components, summary


def _parse_terraform(content: str) -> tuple[list[dict], str]:
    components = []
    # Regex-based extraction for HCL
    resources = re.findall(r'resource\s+"(\w+)"\s+"(\w+)"', content)
    for rtype, rname in resources:
        components.append({"type": "tf_resource", "resource_type": rtype, "name": rname})
    providers = re.findall(r'provider\s+"(\w+)"', content)
    for p in providers:
        components.append({"type": "tf_provider", "name": p})
    variables = re.findall(r'variable\s+"(\w+)"', content)
    for v in variables:
        components.append({"type": "tf_variable", "name": v})
    outputs = re.findall(r'output\s+"(\w+)"', content)
    for o in outputs:
        components.append({"type": "tf_output", "name": o})
    summary = f"Terraform config: {len(resources)} resources, {len(variables)} variables, {len(providers)} providers"
    return components, summary


def _parse_docker_compose(content: str) -> tuple[list[dict], str]:
    data = yaml.safe_load(content)
    components = []
    services = data.get("services", {}) if isinstance(data, dict) else {}
    for svc_name, svc_config in services.items():
        if not isinstance(svc_config, dict):
            continue
        comp = {
            "type": "compose_service",
            "name": svc_name,
            "image": svc_config.get("image", svc_config.get("build", "custom")),
            "ports": svc_config.get("ports", []),
            "volumes": svc_config.get("volumes", []),
            "depends_on": svc_config.get("depends_on", []),
            "environment": list(svc_config.get("environment", {}).keys()) if isinstance(svc_config.get("environment"), dict) else svc_config.get("environment", []),
        }
        components.append(comp)
    networks = list(data.get("networks", {}).keys()) if isinstance(data, dict) else []
    volumes = list(data.get("volumes", {}).keys()) if isinstance(data, dict) else []
    summary = f"Docker Compose: {len(services)} services, {len(networks)} networks, {len(volumes)} volumes"
    return components, summary


def _parse_nginx(content: str) -> tuple[list[dict], str]:
    components = []
    server_blocks = re.findall(r'server\s*\{[^}]*\}', content, re.DOTALL)
    for i, block in enumerate(server_blocks):
        listen = re.findall(r'listen\s+(\S+);', block)
        server_name = re.findall(r'server_name\s+([^;]+);', block)
        locations = re.findall(r'location\s+(\S+)\s*\{', block)
        components.append({
            "type": "nginx_server",
            "index": i,
            "listen": listen,
            "server_name": [s.strip() for sn in server_name for s in sn.split()],
            "locations": locations,
        })
    upstreams = re.findall(r'upstream\s+(\w+)', content)
    for u in upstreams:
        components.append({"type": "nginx_upstream", "name": u})
    summary = f"Nginx config: {len(server_blocks)} server blocks, {len(upstreams)} upstreams"
    return components, summary


def _parse_logs(content: str) -> tuple[list[dict], str]:
    lines = content.strip().splitlines()
    total = len(lines)
    # Count severity levels
    severities: dict[str, int] = {}
    for line in lines:
        for sev in ("CRITICAL", "ERROR", "WARNING", "WARN", "INFO", "DEBUG", "NOTICE", "ALERT", "EMERG"):
            if sev in line.upper():
                severities[sev] = severities.get(sev, 0) + 1
                break
    # Sample first and last 5 lines
    sample = lines[:5] + (["..."] if total > 10 else []) + lines[-5:] if total > 10 else lines
    components = [
        {"type": "log_summary", "total_lines": total, "severities": severities},
        {"type": "log_sample", "lines": sample},
    ]
    summary = f"Log file: {total} lines, severities: {severities}"
    return components, summary


def _parse_network_config(content: str) -> tuple[list[dict], str]:
    components = []
    interfaces = re.findall(r'interface\s+([\w/.-]+)', content, re.IGNORECASE)
    for iface in interfaces:
        components.append({"type": "network_interface", "name": iface})
    routing = re.findall(r'router\s+(ospf|bgp|eigrp)\s*(\d*)', content, re.IGNORECASE)
    for proto, pid in routing:
        components.append({"type": "routing_protocol", "protocol": proto.upper(), "process_id": pid})
    vlans = re.findall(r'vlan\s+(\d+)', content, re.IGNORECASE)
    for v in vlans:
        components.append({"type": "vlan", "id": int(v)})
    summary = f"Network config: {len(interfaces)} interfaces, {len(routing)} routing protocols, {len(vlans)} VLANs"
    return components, summary
