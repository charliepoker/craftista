# Secret Reference Fix - December 27, 2025

## Issue
Pods in the `craftista-prod` namespace were failing with `CreateContainerConfigError` due to incorrect secret references in the deployments.

## Root Cause
The live cluster deployments were referencing incorrect secret names:
- `catalogue-mongodb-secret` (incorrect) → `catalogue-secrets` (correct)
- `recommendation-redis-secret` (incorrect) → `recommendation-secrets` (correct)  
- `voting-postgres-secret` (incorrect) → `voting-secrets` (correct)

## Resolution
Applied kubectl patches to fix the secret references in the live cluster:

```bash
# Fix catalogue deployment
kubectl patch deployment catalogue -n craftista-prod --type='json' \
  -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/env/4/valueFrom/secretKeyRef/name", "value": "catalogue-secrets"}]'

# Fix recommendation deployment  
kubectl patch deployment recommendation -n craftista-prod --type='json' \
  -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/env/0/valueFrom/secretKeyRef/name", "value": "recommendation-secrets"}, {"op": "replace", "path": "/spec/template/spec/containers/0/env/1/valueFrom/secretKeyRef/name", "value": "recommendation-secrets"}, {"op": "replace", "path": "/spec/template/spec/containers/0/env/2/valueFrom/secretKeyRef/name", "value": "recommendation-secrets"}]'

# Fix voting deployment
kubectl patch deployment voting -n craftista-prod --type='json' \
  -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/env/1/valueFrom/secretKeyRef/name", "value": "voting-secrets"}, {"op": "replace", "path": "/spec/template/spec/containers/0/env/2/valueFrom/secretKeyRef/name", "value": "voting-secrets"}, {"op": "replace", "path": "/spec/template/spec/containers/0/env/3/valueFrom/secretKeyRef/name", "value": "voting-secrets"}]'
```

## GitOps Status
✅ The base Kubernetes manifests in this GitOps repository already have the correct secret references.
✅ No changes needed to the GitOps manifests.

## Prevention
- Ensure ArgoCD sync is properly configured to prevent drift
- Use ArgoCD's "hard refresh" to sync from Git when manual changes are detected
- Monitor for configuration drift using ArgoCD's diff view

## Next Steps
- Verify pods are now running correctly
- Address any remaining ImagePullBackOff issues (separate from secret references)
- Ensure ArgoCD is syncing properly to prevent future drift
