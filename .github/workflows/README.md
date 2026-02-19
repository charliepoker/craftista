# GitHub Actions CI/CD Workflows

This directory contains the CI/CD workflows for the Craftista microservices application. Each service has its own dedicated workflow that handles building, testing, security scanning, and deployment.

## Workflows Overview

### 1. Frontend Service (`ci-frontend.yml`)

- **Language**: Node.js 18
- **Tests**: Mocha unit tests with coverage
- **Security Scans**:
  - npm audit for dependency vulnerabilities
  - SonarQube for SAST
  - Trivy for container scanning
- **Docker Image**: `8060633493/craftista-frontend`

### 2. Catalogue Service (`ci-catalogue.yml`)

- **Language**: Python 3.11
- **Tests**: pytest with coverage
- **Security Scans**:
  - Safety and pip-audit for dependency vulnerabilities
  - SonarQube for SAST
  - Trivy for container scanning
- **Docker Image**: `8060633493/craftista-catalogue`

### 3. Voting Service (`ci-voting.yml`)

- **Language**: Java 17 (Maven)
- **Tests**: JUnit with JaCoCo coverage
- **Security Scans**:
  - OWASP Dependency Check
  - SonarQube for SAST
  - Trivy for container scanning
- **Docker Image**: `8060633493/craftista-voting`

### 4. Recommendation Service (`ci-recommendation.yml`)

- **Language**: Go 1.19
- **Tests**: Go test with race detection and coverage
- **Security Scans**:
  - govulncheck for Go vulnerabilities
  - SonarQube for SAST
  - Trivy for container scanning
- **Docker Image**: `8060633493/craftista-recommendation`

### 5. Shared GitOps Update Workflow (`update-gitops.yml`)

This is a reusable workflow that handles updating the GitOps repository with new image tags. It's called by all service CI workflows after successful builds.

**Features**:

- Authenticates with HashiCorp Vault to retrieve GitOps repository credentials
- Updates both Kubernetes overlays and Helm values files
- Handles merge conflicts gracefully with retry logic
- Provides detailed logging and error handling
- Supports both SSH deploy keys and Personal Access Tokens

**Inputs**:

- `service-name`: Name of the microservice (frontend, catalogue, voting, recommendation)
- `environment`: Target environment (dev, staging, prod)
- `image-tag`: Docker image tag to deploy
- `docker-image`: Full Docker image name
- `commit-sha`: Git commit SHA for traceability
- `branch-name`: Git branch name for traceability

**Secrets**:

- `VAULT_ADDR`: HashiCorp Vault server address
- `VAULT_TOKEN`: Vault authentication token

## Workflow Stages

Each service workflow follows the same pattern:

1. **Build and Test**: Compile code and run unit tests
2. **Dependency Scan**: Check for vulnerable dependencies
3. **SAST Scan**: Static application security testing with SonarQube
4. **Build Image**: Build and push Docker image to DockerHub
5. **Container Scan**: Scan Docker image with Trivy
6. **Determine Environment**: Map Git branch to deployment environment
7. **Update GitOps**: Call reusable workflow to update craftista-gitOps repository
8. **Notify**: Send build status notification

## Triggers

Workflows are triggered on:

- **Push** to `develop`, `staging`, or `main` branches
- **Pull Request** to `develop`, `staging`, or `main` branches
- Only when files in the service directory or workflow file change

## Environment Mapping

- `develop` branch → `dev` environment
- `staging` branch → `staging` environment
- `main` branch → `prod` environment

## Required GitHub Secrets

The following secrets must be configured in your GitHub repository:

### DockerHub Credentials

- `DOCKERHUB_USERNAME`: Your DockerHub username
- `DOCKERHUB_TOKEN`: DockerHub access token (not password)

### SonarQube Configuration

- `SONAR_TOKEN`: SonarQube authentication token
- `SONAR_HOST_URL`: SonarQube server URL (e.g., `https://sonarqube.example.com`)

### HashiCorp Vault Configuration

- `VAULT_ADDR`: HashiCorp Vault server address (e.g., `https://vault.example.com`)
- `VAULT_TOKEN`: Vault authentication token for GitHub Actions

### GitOps Repository Access (Stored in Vault)

The GitOps repository credentials are stored in Vault at the following paths:

- `secret/github-actions/gitops-deploy-key`: SSH private key for GitOps repository (preferred)
- `secret/github-actions/gitops-pat`: GitHub Personal Access Token (fallback)

## Image Tagging Strategy

Images are tagged with multiple tags:

- **Branch name**: `develop`, `staging`, `main`
- **Commit SHA**: `{branch}-{sha}` (e.g., `develop-abc1234`)
- **Latest**: Only for the default branch (`main`)

Example:

```
8060633493/craftista-frontend:develop
8060633493/craftista-frontend:develop-abc1234567890
8060633493/craftista-frontend:latest (only on main branch)
```

## GitOps Integration

After a successful build and scan, the reusable `update-gitops.yml` workflow:

1. **Authenticates with Vault** to retrieve GitOps repository credentials
2. **Validates inputs** to ensure service name and environment are valid
3. **Clones the GitOps repository** using SSH deploy key or PAT from Vault
4. **Updates Kubernetes overlays** by modifying `kustomization.yaml` files
5. **Updates Helm values** by modifying environment-specific values files
6. **Commits and pushes changes** with descriptive commit messages
7. **Handles conflicts** with automatic retry and rebase logic
8. **Provides notifications** on success or failure

The workflow supports both Kubernetes overlays (using Kustomize) and Helm charts, automatically detecting which approach is used for each service.

## Security Features

### Vulnerability Scanning

- **Dependency scanning** catches vulnerable libraries before deployment
- **SAST scanning** identifies code quality and security issues
- **Container scanning** finds vulnerabilities in the final Docker image

### Quality Gates

- SonarQube quality gate checks code quality metrics
- Critical vulnerabilities fail the build
- Coverage reports are generated for all services

### Least Privilege

- Workflows only have access to required secrets
- GitOps updates use a dedicated PAT with minimal permissions
- Container images run as non-root users

## Troubleshooting

### Build Failures

- Check the specific job that failed in the GitHub Actions UI
- Review test output and error messages
- Ensure all dependencies are correctly specified

### Security Scan Failures

- Review the security scan reports in the artifacts
- Update vulnerable dependencies
- For false positives, configure suppressions in the respective tools

### GitOps Update Failures

- Verify the `GITOPS_PAT` secret has write access
- Check that the `craftista-gitOps` repository exists
- Ensure the overlay directory structure matches expectations

### Docker Push Failures

- Verify DockerHub credentials are correct
- Check DockerHub rate limits
- Ensure the repository exists and you have push access

## Local Testing

To test workflows locally before pushing:

### Validate YAML syntax

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci-frontend.yml'))"
```

### Run tests locally

```bash
# Frontend
cd frontend && npm test

# Catalogue
cd catalogue && pytest

# Voting
cd voting && mvn test

# Recommendation
cd recommendation && go test ./...
```

### Build Docker images locally

```bash
# Frontend
docker build -t craftista-frontend:local ./frontend

# Catalogue
docker build -t craftista-catalogue:local ./catalogue

# Voting
docker build -t craftista-voting:local ./voting

# Recommendation
docker build -t craftista-recommendation:local ./recommendation
```

## Monitoring

- View workflow runs in the GitHub Actions tab
- Check build status badges (can be added to README)
- Review security scan results in GitHub Security tab
- Monitor ArgoCD for deployment status

## Next Steps

1. Configure all required secrets in GitHub repository settings
2. Set up SonarQube server and create project tokens
3. Create the `craftista-gitOps` repository with proper structure
4. Test workflows by pushing changes to a feature branch
5. Monitor the first deployment to ensure everything works correctly

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Build Push Action](https://github.com/docker/build-push-action)
- [Trivy Action](https://github.com/aquasecurity/trivy-action)
- [SonarQube Scan Action](https://github.com/SonarSource/sonarqube-scan-action)
