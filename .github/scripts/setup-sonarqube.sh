#!/bin/bash

# SonarQube Setup Script for Raspberry Pi Homelab
# This script deploys SonarQube on Kubernetes with PostgreSQL backend

set -e

NAMESPACE="${SONARQUBE_NAMESPACE:-sonarqube}"
SONARQUBE_VERSION="${SONARQUBE_VERSION:-10.3.0-community}"
POSTGRES_VERSION="${POSTGRES_VERSION:-15-alpine}"
STORAGE_CLASS="${STORAGE_CLASS:-local-path}"
SONARQUBE_DOMAIN="${SONARQUBE_DOMAIN:-sonarqube.local}"

echo "🚀 Setting up SonarQube on Kubernetes"
echo "Namespace: $NAMESPACE"
echo "SonarQube Version: $SONARQUBE_VERSION"
echo "Domain: $SONARQUBE_DOMAIN"

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl not found. Please install kubectl first."
    exit 1
fi

# Check cluster connectivity
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster"
    exit 1
fi

echo "✅ Connected to Kubernetes cluster"

# Create namespace
echo "📦 Creating namespace..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# Create PostgreSQL password secret
echo "🔐 Creating secrets..."
POSTGRES_PASSWORD=$(openssl rand -base64 32)
SONARQUBE_JDBC_PASSWORD=$(openssl rand -base64 32)

kubectl create secret generic sonarqube-postgres \
    --from-literal=postgres-password="$POSTGRES_PASSWORD" \
    --from-literal=password="$SONARQUBE_JDBC_PASSWORD" \
    --namespace="$NAMESPACE" \
    --dry-run=client -o yaml | kubectl apply -f -

echo "✅ Secrets created"

# Create PostgreSQL PVC
echo "💾 Creating PostgreSQL PersistentVolumeClaim..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: sonarqube-postgres-pvc
  namespace: $NAMESPACE
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: $STORAGE_CLASS
  resources:
    requests:
      storage: 10Gi
EOF

# Create SonarQube PVC
echo "💾 Creating SonarQube PersistentVolumeClaims..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: sonarqube-data-pvc
  namespace: $NAMESPACE
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: $STORAGE_CLASS
  resources:
    requests:
      storage: 10Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: sonarqube-extensions-pvc
  namespace: $NAMESPACE
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: $STORAGE_CLASS
  resources:
    requests:
      storage: 5Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: sonarqube-logs-pvc
  namespace: $NAMESPACE
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: $STORAGE_CLASS
  resources:
    requests:
      storage: 5Gi
EOF

echo "✅ PVCs created"

# Deploy PostgreSQL
echo "🐘 Deploying PostgreSQL..."
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sonarqube-postgres
  namespace: $NAMESPACE
  labels:
    app: sonarqube-postgres
spec:
  replicas: 1
  selector:
    matchLabels:
      app: sonarqube-postgres
  template:
    metadata:
      labels:
        app: sonarqube-postgres
    spec:
      containers:
      - name: postgres
        image: postgres:$POSTGRES_VERSION
        ports:
        - containerPort: 5432
          name: postgres
        env:
        - name: POSTGRES_DB
          value: sonarqube
        - name: POSTGRES_USER
          value: sonarqube
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: sonarqube-postgres
              key: password
        - name: PGDATA
          value: /var/lib/postgresql/data/pgdata
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          exec:
            command:
            - pg_isready
            - -U
            - sonarqube
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          exec:
            command:
            - pg_isready
            - -U
            - sonarqube
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: sonarqube-postgres-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: sonarqube-postgres
  namespace: $NAMESPACE
  labels:
    app: sonarqube-postgres
spec:
  type: ClusterIP
  ports:
  - port: 5432
    targetPort: 5432
    protocol: TCP
    name: postgres
  selector:
    app: sonarqube-postgres
EOF

echo "✅ PostgreSQL deployed"

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/sonarqube-postgres -n "$NAMESPACE"

# Deploy SonarQube
echo "📊 Deploying SonarQube..."
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sonarqube
  namespace: $NAMESPACE
  labels:
    app: sonarqube
spec:
  replicas: 1
  selector:
    matchLabels:
      app: sonarqube
  template:
    metadata:
      labels:
        app: sonarqube
    spec:
      initContainers:
      - name: init-sysctl
        image: busybox:1.36
        command:
        - sh
        - -c
        - |
          sysctl -w vm.max_map_count=524288
          sysctl -w fs.file-max=131072
          ulimit -n 131072
          ulimit -u 8192
        securityContext:
          privileged: true
      containers:
      - name: sonarqube
        image: sonarqube:$SONARQUBE_VERSION
        ports:
        - containerPort: 9000
          name: http
        env:
        - name: SONAR_JDBC_URL
          value: jdbc:postgresql://sonarqube-postgres:5432/sonarqube
        - name: SONAR_JDBC_USERNAME
          value: sonarqube
        - name: SONAR_JDBC_PASSWORD
          valueFrom:
            secretKeyRef:
              name: sonarqube-postgres
              key: password
        - name: SONAR_WEB_JAVAADDITIONALOPTS
          value: "-Xmx512m -Xms128m"
        - name: SONAR_CE_JAVAADDITIONALOPTS
          value: "-Xmx512m -Xms128m"
        volumeMounts:
        - name: sonarqube-data
          mountPath: /opt/sonarqube/data
        - name: sonarqube-extensions
          mountPath: /opt/sonarqube/extensions
        - name: sonarqube-logs
          mountPath: /opt/sonarqube/logs
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "3Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /api/system/status
            port: 9000
          initialDelaySeconds: 120
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 6
        readinessProbe:
          httpGet:
            path: /api/system/status
            port: 9000
          initialDelaySeconds: 60
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 6
      volumes:
      - name: sonarqube-data
        persistentVolumeClaim:
          claimName: sonarqube-data-pvc
      - name: sonarqube-extensions
        persistentVolumeClaim:
          claimName: sonarqube-extensions-pvc
      - name: sonarqube-logs
        persistentVolumeClaim:
          claimName: sonarqube-logs-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: sonarqube
  namespace: $NAMESPACE
  labels:
    app: sonarqube
spec:
  type: LoadBalancer
  ports:
  - port: 9000
    targetPort: 9000
    protocol: TCP
    name: http
  selector:
    app: sonarqube
EOF

echo "✅ SonarQube deployed"

# Wait for SonarQube to be ready
echo "⏳ Waiting for SonarQube to be ready (this may take several minutes)..."
kubectl wait --for=condition=available --timeout=600s deployment/sonarqube -n "$NAMESPACE" || true

# Get service information
echo ""
echo "🎉 SonarQube deployment complete!"
echo ""
echo "📋 Service Information:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Get LoadBalancer IP or NodePort
SERVICE_TYPE=$(kubectl get svc sonarqube -n "$NAMESPACE" -o jsonpath='{.spec.type}')
if [ "$SERVICE_TYPE" == "LoadBalancer" ]; then
    EXTERNAL_IP=$(kubectl get svc sonarqube -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    if [ -z "$EXTERNAL_IP" ]; then
        echo "⏳ Waiting for LoadBalancer IP..."
        sleep 10
        EXTERNAL_IP=$(kubectl get svc sonarqube -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    fi
    if [ -n "$EXTERNAL_IP" ]; then
        echo "SonarQube URL: http://$EXTERNAL_IP:9000"
    else
        echo "⚠️  LoadBalancer IP not yet assigned"
        echo "Run: kubectl get svc sonarqube -n $NAMESPACE"
    fi
else
    NODE_PORT=$(kubectl get svc sonarqube -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].nodePort}')
    NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
    echo "SonarQube URL: http://$NODE_IP:$NODE_PORT"
fi

echo ""
echo "Default credentials:"
echo "  Username: admin"
echo "  Password: admin"
echo "  (You will be prompted to change this on first login)"
echo ""
echo "PostgreSQL credentials saved in secret: sonarqube-postgres"
echo ""
echo "To access SonarQube:"
echo "  kubectl port-forward -n $NAMESPACE svc/sonarqube 9000:9000"
echo "  Then open: http://localhost:9000"
echo ""
echo "To check logs:"
echo "  kubectl logs -n $NAMESPACE -l app=sonarqube -f"
echo ""
echo "To get admin token for CI/CD:"
echo "  1. Login to SonarQube"
echo "  2. Go to: My Account → Security → Generate Tokens"
echo "  3. Create a token named 'github-actions'"
echo "  4. Save the token as GitHub secret: SONAR_TOKEN"
echo ""
