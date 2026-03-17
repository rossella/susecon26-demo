#!/bin/bash
set -e

echo "🚀 Deploying ilovegeekos to Rancher Desktop..."

# Change to workspace directory
cd "$(dirname "$0")"

# Step 1: Build the image
echo ""
echo "📦 Building Docker image..."
docker build -t ilovegeekos:latest .

# Step 2: Set kubectl context
echo ""
echo "🔗 Setting kubectl context to rancher-desktop..."
kubectl config use-context rancher-desktop

# Step 3: Deploy Kubernetes manifests
echo ""
echo "📋 Creating namespace..."
kubectl apply -f k8s/namespace.yaml

echo ""
echo "⚙️  Applying ConfigMap (Redis backend enabled)..."
kubectl apply -f k8s/configmap.yaml

echo ""
echo "💾 Creating PersistentVolumeClaim..."
kubectl apply -f k8s/pvc.yaml

echo ""
echo "🔴 Deploying Redis..."
kubectl apply -f k8s/redis.yaml

echo ""
echo "🦎 Deploying application..."
kubectl apply -f k8s/deployment.yaml

echo ""
echo "🌐 Creating service..."
kubectl apply -f k8s/service.yaml

# Step 4: Wait for deployment
echo ""
echo "⏳ Waiting for pods to be ready..."
kubectl rollout status deployment/ilovegeekos -n ilovegeekos --timeout=2m
kubectl rollout status deployment/redis -n ilovegeekos --timeout=2m

# Step 5: Show status
echo ""
echo "✅ Deployment complete! Status:"
kubectl get all -n ilovegeekos

echo ""
echo "📊 To check Redis memory usage, run:"
echo "   kubectl port-forward -n ilovegeekos svc/ilovegeekos 5000:80"
echo "   Then visit: http://localhost:5000/storage-status"

echo ""
echo "🎉 All set! Your app is running on Rancher Desktop with Redis backend."
