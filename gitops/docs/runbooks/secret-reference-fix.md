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

## Resolution Status

### ✅ Completed
- Fixed secret reference issues in cluster deployments
- Frontend service is running successfully (3/3 pods)
- Cleaned up failed pods and replicasets

### ⚠️ Remaining Issues
- **Image Pull Authentication**: Backend services (catalogue, recommendation, voting) failing with 401 Unauthorized errors
- **Root Cause**: Docker Hub registry requires authentication for private repositories
- **Current Status**: Backend services scaled to 0 replicas to prevent resource waste

### 🔧 Temporary Resolution
```bash
# Scaled down problematic services
kubectl scale deployment catalogue recommendation voting -n craftista-prod --replicas=0
```

### 📋 Next Steps
1. **Fix Docker Registry Authentication**:
   - Verify `dockerhub-pull-secret` is valid and not expired
   - Update Docker Hub credentials if needed
   - Or migrate to public images/different registry

2. **Alternative Solutions**:
   - Build and push images to ECR (AWS Container Registry)
   - Use public base images for development
   - Set up proper CI/CD pipeline for image builds

3. **Scale Services Back Up**:
   ```bash
   kubectl scale deployment catalogue recommendation voting -n craftista-prod --replicas=3
   ```

### 🎯 Current Working Services
- ✅ Frontend: 3/3 pods running successfully
- ❌ Catalogue: 0/3 (scaled down due to image pull issues)
- ❌ Recommendation: 0/3 (scaled down due to image pull issues)  
- ❌ Voting: 0/3 (scaled down due to image pull issues)
