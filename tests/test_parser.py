"""Tests for config parser — detection and extraction."""

import pytest
from app.models.schemas import ConfigType
from app.parsers.config_parser import detect_config_type, parse_config


# ---------------------------------------------------------------------------
# Detection tests
# ---------------------------------------------------------------------------

class TestDetection:
    def test_kubernetes_manifest(self):
        content = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx
spec:
  replicas: 3"""
        assert detect_config_type(content) == ConfigType.KUBERNETES

    def test_terraform(self):
        content = '''resource "aws_instance" "web" {
  ami           = "ami-12345"
  instance_type = "t3.micro"
}'''
        assert detect_config_type(content) == ConfigType.TERRAFORM

    def test_docker_compose(self):
        content = """services:
  web:
    image: nginx:latest
    ports:
      - "80:80"
"""
        assert detect_config_type(content) == ConfigType.DOCKER_COMPOSE

    def test_ansible_playbook(self):
        content = """- name: Install packages
  hosts: all
  tasks:
    - name: Install nginx
      apt:
        name: nginx
        state: present"""
        assert detect_config_type(content) == ConfigType.ANSIBLE_PLAYBOOK

    def test_nginx_config(self):
        content = """server {
    listen 80;
    server_name example.com;
    location / {
        proxy_pass http://backend;
    }
}"""
        assert detect_config_type(content) == ConfigType.NGINX

    def test_network_config(self):
        content = """interface GigabitEthernet0/1
 ip address 10.0.0.1 255.255.255.0
 no shutdown
router ospf 1
 network 10.0.0.0 0.0.0.255 area 0"""
        assert detect_config_type(content) == ConfigType.NETWORK_CONFIG

    def test_syslog(self):
        content = """<134>Mar 15 10:30:01 web01 nginx: 200 GET /api/health
<131>Mar 15 10:30:02 db01 postgres: ERROR: connection refused"""
        assert detect_config_type(content) == ConfigType.SYSLOG

    def test_systemd_unit(self):
        content = """[Unit]
Description=My Service
After=network.target

[Service]
ExecStart=/usr/bin/myapp
Restart=always"""
        assert detect_config_type(content) == ConfigType.SYSTEMD

    def test_filename_terraform(self):
        assert detect_config_type("foo = bar", "main.tf") == ConfigType.TERRAFORM

    def test_filename_compose(self):
        assert detect_config_type("services:", "docker-compose.yml") == ConfigType.DOCKER_COMPOSE

    def test_generic_fallback(self):
        assert detect_config_type("hello world") == ConfigType.GENERIC


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

class TestParser:
    def test_parse_kubernetes(self):
        content = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  namespace: production
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: app
          image: myapp:1.0
          ports:
            - containerPort: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: web-svc
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: 8080"""
        result = parse_config(content, ConfigType.KUBERNETES)
        assert result.config_type == ConfigType.KUBERNETES
        assert len(result.components) == 2
        assert "1x Deployment" in result.summary
        assert "1x Service" in result.summary

    def test_parse_terraform(self):
        content = '''provider "aws" {
  region = "us-east-1"
}

resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_subnet" "public" {
  vpc_id     = aws_vpc.main.id
  cidr_block = "10.0.1.0/24"
}

variable "environment" {
  default = "production"
}

output "vpc_id" {
  value = aws_vpc.main.id
}'''
        result = parse_config(content, ConfigType.TERRAFORM)
        assert result.config_type == ConfigType.TERRAFORM
        assert "2 resources" in result.summary
        assert "1 variables" in result.summary

    def test_parse_docker_compose(self):
        content = """services:
  web:
    image: nginx:latest
    ports:
      - "80:80"
    depends_on:
      - api
  api:
    image: myapi:1.0
    ports:
      - "8000:8000"
networks:
  frontend:
volumes:
  data:"""
        result = parse_config(content, ConfigType.DOCKER_COMPOSE)
        assert result.config_type == ConfigType.DOCKER_COMPOSE
        assert "2 services" in result.summary
        assert "1 networks" in result.summary

    def test_parse_ansible(self):
        content = """- name: Setup web servers
  hosts: webservers
  vars:
    http_port: 80
  tasks:
    - name: Install nginx
      apt:
        name: nginx
    - name: Start nginx
      service:
        name: nginx
        state: started"""
        result = parse_config(content, ConfigType.ANSIBLE_PLAYBOOK)
        assert result.config_type == ConfigType.ANSIBLE_PLAYBOOK
        assert "1 play(s)" in result.summary
        assert "2 task(s)" in result.summary

    def test_parse_logs(self):
        lines = ["INFO line " + str(i) for i in range(20)]
        lines[5] = "ERROR something broke"
        lines[10] = "WARNING disk space low"
        content = "\n".join(lines)
        result = parse_config(content, ConfigType.SYSLOG)
        assert result.config_type == ConfigType.SYSLOG
        assert "20 lines" in result.summary

    def test_auto_detect_and_parse(self):
        content = """apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  key: value"""
        result = parse_config(content, ConfigType.AUTO_DETECT)
        assert result.config_type == ConfigType.KUBERNETES

    def test_empty_content_graceful(self):
        result = parse_config("", ConfigType.GENERIC)
        assert result.config_type == ConfigType.GENERIC
