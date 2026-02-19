# Craftista Homelab CI/CD + GitOps Setup (GitHub Actions → Argo CD)

This guide matches the current state of your Craftista project:

- Local GitOps repo: `~/Documents/craftista-gitOps`
- Local homelab/cluster repo: `~/Documents/k8s-raspberrypi-homelab`
- 3-node Raspberry Pi Kubernetes cluster
- Vault + SonarQube running on `k8s-worker-1` (`10.0.0.248`)
- CI runs on GitHub-hosted runners and pushes image tags + GitOps updates

Important: avoid storing passwords or long-lived admin tokens in docs or repos. Use SSH keys, least-privilege tokens, and Vault policies.

---

## How the pipeline works

1. Developer pushes to `develop`, `staging`, or `main`.
2. GitHub Actions builds/tests each service and runs security scans.
3. GitHub Actions builds and pushes images to DockerHub.
4. GitHub Actions updates the GitOps repo manifests (Kustomize/Helm) with the new image tag.
5. Argo CD detects the GitOps change and syncs to your cluster.
6. GitHub Actions optionally verifies the deployment via Kubernetes API.

---

## Branch → environment mapping

- `develop` → `dev`
- `staging` → `staging`
- `main` → `prod`

These names must align across:

- GitHub Actions
- GitOps repo directory layout
- Kubernetes namespaces (`craftista-dev`, `craftista-staging`, `craftista-prod`)
- Argo CD Application names (`<service>-<env>`)

---

## Workflow files in this repo

Service CI/CD:

- `ci-frontend.yml` (Node)
- `ci-catalogue.yml` (Python)
- `ci-voting.yml` (Java/Maven)
- `ci-recommendation.yml` (Go)

Shared/reusable:

- `update-gitops.yml` (called by each service workflow)
- `verify-deployment.yml` (reusable deployment verification)

Manual operations:

- `rollback-deployment.yml` (manual rollback)

Extra testing:

- `database-tests.yml` (runs DB-backed integration tests on PRs/push)

Note: `production-pipeline.yml` exists in this repo but is not required for the current per-service pipelines.

---

## Prerequisites (one-time)

### A) DockerHub

- A DockerHub account and a token that can push to:
  - `8060633493/craftista-frontend`
  - `8060633493/craftista-catalogue`
  - `8060633493/craftista-voting`
  - `8060633493/craftista-recommendation`

### B) SonarQube

- SonarQube reachable by GitHub-hosted runners via `SONAR_HOST_URL`
- A SonarQube token (`SONAR_TOKEN`) with permission to analyze projects:
  - `craftista-frontend`
  - `craftista-catalogue`
  - `craftista-voting`
  - `craftista-recommendation`

### C) Vault

- Vault reachable by GitHub Actions via `VAULT_ADDR`
- A Vault token used by GitHub Actions (`VAULT_TOKEN`)

Minimum required Vault secret paths (KV v2):

- `secret/github-actions/gitops-deploy-key` (field: `private_key`) OR
- `secret/github-actions/gitops-pat` (field: `token`)
- `secret/kubernetes/dev/kubeconfig` (field: `config`)
- `secret/kubernetes/staging/kubeconfig` (field: `config`)
- `secret/kubernetes/prod/kubeconfig` (field: `config`)

### D) GitOps repo

Your GitOps repo must exist on GitHub and match the repo name in `update-gitops.yml`:

- `8060633493/craftista-gitOps`

If your GitOps repo is named differently, update `env.GITOPS_REPO` in `update-gitops.yml` (and `rollback-deployment.yml` if you use GitOps rollback).

---

## Step 1 — GitOps repository structure (required)

`update-gitops.yml` updates image tags in **Kustomize overlays** and/or **Helm values**.

### Kustomize overlays (recommended)

For each service and environment, create:

```
kubernetes/overlays/<env>/<service>/kustomization.yaml
```

Example (Catalogue, dev):

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: craftista-dev

resources:
  - ../../../base/catalogue

images:
  - name: 8060633493/craftista-catalogue
    newTag: develop
```

Repeat for:

- `kubernetes/overlays/dev/<service>`
- `kubernetes/overlays/staging/<service>`
- `kubernetes/overlays/prod/<service>`

### Helm (optional)

If you use Helm for a service, `update-gitops.yml` also tries:

```
helm/charts/<service>/values-<env>.yaml
```

---

## Step 2 — GitOps repo credentials (Deploy Key or PAT)

`update-gitops.yml` and the GitOps rollback path in `rollback-deployment.yml` prefer an SSH deploy key stored in Vault and fall back to a PAT.

### Option A (recommended): SSH deploy key

1. Generate a dedicated keypair:

```bash
mkdir -p ~/.ssh
ssh-keygen -t ed25519 -C "github-actions-gitops" -f ~/.ssh/gitops_deploy_key -N ""
```

2. Add the public key to the `craftista-gitOps` repo:

- GitHub → `craftista-gitOps` repo → Settings → Deploy keys → Add deploy key
- Paste `~/.ssh/gitops_deploy_key.pub`
- ✅ Enable **Allow write access**

3. Store the private key in Vault:

```bash
vault kv put secret/github-actions/gitops-deploy-key \
  private_key="$(cat ~/.ssh/gitops_deploy_key)"
```

### Option B: fine‑grained PAT (fallback)

Create a fine‑grained token limited to `craftista-gitOps` with:

- Repository permissions → Contents: Read and write

Store it in Vault:

```bash
vault kv put secret/github-actions/gitops-pat \
  token="ghp_..."
```

---

## Step 3 — Store kubeconfigs in Vault (required for verify/rollback)

The verification and rollback workflows read kubeconfig from:

- `secret/kubernetes/<env>/kubeconfig` field `config`

Example:

```bash
vault kv put secret/kubernetes/dev/kubeconfig \
  config="$(cat ~/.kube/config-dev)"
```

Repeat for `staging` and `prod`.

---

## Step 4 — GitHub Actions secrets (required)

In the `craftista` repo → Settings → Secrets and variables → Actions:

Required:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`
- `VAULT_ADDR`
- `VAULT_TOKEN`

SonarQube (if you want scans):

- `SONAR_HOST_URL`
- `SONAR_TOKEN`

Optional:

- `SLACK_WEBHOOK_URL`

---

## Step 5 — Argo CD (high-level requirements)

For GitOps to work end-to-end, you need:

- Argo CD installed in namespace `argocd`
- Namespaces created: `craftista-dev`, `craftista-staging`, `craftista-prod`
- Argo CD Applications named `<service>-<env>` (example: `catalogue-dev`)
- Applications pointing at the GitOps repo overlay paths:
  - `kubernetes/overlays/<env>/<service>`

---

## Step 6 — First run / smoke test

1. Ensure SonarQube projects exist and match workflow project keys.
2. Push a small change to trigger each service workflow:

- Change `frontend/**` → triggers `ci-frontend.yml`
- Change `catalogue/**` → triggers `ci-catalogue.yml`
- Change `voting/**` → triggers `ci-voting.yml`
- Change `recommendation/**` → triggers `ci-recommendation.yml`

3. Confirm the `Update GitOps Repository` job runs and commits/pushes to `craftista-gitOps`.
4. Confirm Argo CD syncs and the workload in `craftista-<env>` uses the new tag.

---

## Troubleshooting

### GitOps update fails

Common causes:

- Vault token can’t read `secret/github-actions/*` paths
- Missing `kubernetes/overlays/<env>/<service>` directories in GitOps repo
- Deploy key exists but did not have **Allow write access**

### Verify deployment fails

- Missing kubeconfig in Vault at `secret/kubernetes/<env>/kubeconfig`
- Namespace mismatch (expected `craftista-<env>`)
- Deployment/service name mismatch (expected deployment named exactly `<service>`)

---

## Security notes (strongly recommended)

- Prefer SSH deploy keys over PATs for repo write access.
- Use a dedicated low-privilege Vault token for GitHub Actions with a tight policy.
- Prefer Vault AppRole or GitHub OIDC integration instead of long-lived tokens when you’re ready.
