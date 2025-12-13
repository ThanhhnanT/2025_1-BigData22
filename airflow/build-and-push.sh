#!/bin/bash
# Script để build và push Airflow image lên Docker Hub
# Usage: ./build-and-push.sh [dockerhub-username] [tag]
# Example: ./build-and-push.sh myusername latest
#          ./build-and-push.sh myusername v1.0.0

set -e

# Get Docker Hub username from argument or environment variable
DOCKERHUB_USERNAME="${1:-${DOCKERHUB_USERNAME}}"
TAG="${2:-latest}"

if [ -z "$DOCKERHUB_USERNAME" ]; then
    echo "❌ Error: Docker Hub username is required"
    echo ""
    echo "Usage:"
    echo "  ./build-and-push.sh <dockerhub-username> [tag]"
    echo ""
    echo "Or set environment variable:"
    echo "  export DOCKERHUB_USERNAME=your-username"
    echo "  ./build-and-push.sh [tag]"
    echo ""
    exit 1
fi

IMAGE_NAME="${DOCKERHUB_USERNAME}/crypto-airflow"
FULL_IMAGE_NAME="${IMAGE_NAME}:${TAG}"

echo "🐳 Building and pushing Airflow image to Docker Hub"
echo "   Username: $DOCKERHUB_USERNAME"
echo "   Image: $FULL_IMAGE_NAME"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Check if logged in to Docker Hub
if ! docker info | grep -q "Username"; then
    echo "⚠️  Not logged in to Docker Hub. Please login:"
    echo "   docker login"
    echo ""
    read -p "Press Enter after logging in, or Ctrl+C to cancel..."
fi

# Build image
echo "🔨 Building image: $FULL_IMAGE_NAME"
docker build -t "$FULL_IMAGE_NAME" -f Dockerfile .

# Also tag as latest if not already
if [ "$TAG" != "latest" ]; then
    echo "🏷️  Tagging as latest..."
    docker tag "$FULL_IMAGE_NAME" "${IMAGE_NAME}:latest"
fi

# Push image
echo "📤 Pushing image to Docker Hub..."
docker push "$FULL_IMAGE_NAME"

if [ "$TAG" != "latest" ]; then
    echo "📤 Pushing latest tag..."
    docker push "${IMAGE_NAME}:latest"
fi

echo ""
echo "✅ Successfully pushed image to Docker Hub!"
echo ""
echo "📋 Image details:"
echo "   - $FULL_IMAGE_NAME"
if [ "$TAG" != "latest" ]; then
    echo "   - ${IMAGE_NAME}:latest"
fi
echo ""
echo "🔧 To use this image, update deploy/helm/values-minikube.yaml:"
echo "   images:"
echo "     airflow:"
echo "       repository: ${DOCKERHUB_USERNAME}/crypto-airflow"
echo "       tag: ${TAG}"
echo ""

