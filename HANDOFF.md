# Claude Code Handoff — DK InfraEdge DocGen MVP

## Context
DK InfraEdge's first AI tool — an automated documentation generator. Takes infrastructure configs/logs as input, generates clean professional documentation using LLM.

Pre-built files are in ~/docgen-mvp/. DO NOT explore or rewrite them — integrate as-is.

Repos:
- New repo to create: github.com/eched1/docgen (or dk-docgen)
- GitOps: ~/homelab-gitops (github.com/eched1/homelab-gitops)
- Deploy to k3s in `logsight` namespace alongside existing services

## Task 1: Create GitHub repo and push code

1. `cd ~/ && cp -r docgen-mvp docgen && cd docgen`
2. `git init && git add -A && git commit -m "DocGen MVP: config parser + LLM doc generator"`
3. `gh repo create eched1/docgen --public --source=. --push`

## Task 2: Run tests

1. `cd ~/docgen`
2. `pip install -r requirements.txt`
3. `python -m pytest tests/ -v`
4. Verify 18/18 pass

## Task 3: Create k8s secret for OpenAI API key

```bash
kubectl -n logsight create secret generic docgen-secrets \
  --from-literal=OPENAI_API_KEY="${OPENAI_API_KEY}"
```

If no OPENAI_API_KEY env var is set, ask the user or skip — the app has a fallback mode without AI.

## Task 4: Add to homelab-gitops

1. `cd ~/homelab-gitops`
2. `mkdir -p apps/docgen`
3. `cp ~/docgen/k8s/* apps/docgen/`
4. Add docgen to any root kustomization or ArgoCD Application if needed
5. `git add apps/docgen/ && git commit -m "Add DocGen MVP to GitOps" && git push`

## Task 5: Build and deploy

1. `cd ~/docgen`
2. `sudo docker build -t docgen:0.1.0 .`
3. `sudo docker save docgen:0.1.0 -o /tmp/docgen-0.1.0.tar`
4. Distribute: `for node in k3s-cp-01 k3s-wk-01 k3s-wk-02; do scp /tmp/docgen-0.1.0.tar $node:/tmp/ && ssh $node "sudo ctr -n k8s.io images import /tmp/docgen-0.1.0.tar"; done`
5. Apply: `kubectl apply -k ~/homelab-gitops/apps/docgen/`
6. Wait: `kubectl -n logsight rollout status deployment/docgen`

## Task 6: Add DNS entry (if CoreDNS manages home.arpa)

Add `docgen.home.arpa` pointing to the MetalLB VIP (192.168.1.50) or verify ingress picks it up automatically.

## Task 7: Smoke test

```bash
# Health check
curl -s https://docgen.home.arpa/health --cacert /etc/ssl/certs/lan-ca.crt

# List supported formats
curl -s https://docgen.home.arpa/api/v1/formats --cacert /etc/ssl/certs/lan-ca.crt | python -m json.tool

# Generate docs from a k8s manifest
curl -X POST https://docgen.home.arpa/api/v1/generate \
  --cacert /etc/ssl/certs/lan-ca.crt \
  -F "file=@/path/to/any/deployment.yaml" \
  -F "doc_style=technical" \
  -F "include_diagram=true" | python -m json.tool

# Generate from raw text
curl -X POST https://docgen.home.arpa/api/v1/generate/text \
  --cacert /etc/ssl/certs/lan-ca.crt \
  -H "Content-Type: application/json" \
  -d '{"config_type":"auto_detect","doc_style":"runbook","raw_config":"apiVersion: v1\nkind: Service\nmetadata:\n  name: test\nspec:\n  ports:\n    - port: 80"}'
```

## Validation

- [ ] GitHub repo created and code pushed
- [ ] 18/18 tests pass
- [ ] k8s secret created (or fallback mode confirmed)
- [ ] Deployment running in logsight namespace
- [ ] /health returns 200
- [ ] /api/v1/formats returns config types and doc styles
- [ ] File upload generates documentation
- [ ] Ingress accessible at docgen.home.arpa
