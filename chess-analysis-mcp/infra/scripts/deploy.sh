#!/usr/bin/env bash
# Deploy chess-analysis-mcp to AWS ECS Fargate
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
ECR_REPO="${ECR_REPO:-chess-analysis-mcp}"
ECS_CLUSTER="${ECS_CLUSTER:-chess-analysis}"
ECS_SERVICE="${ECS_SERVICE:-chess-analysis-mcp}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Build and push Docker image to ECR
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"

echo "Logging in to ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | \
    docker login --username AWS --password-stdin "${ECR_URI}"

echo "Building Docker image..."
docker build -t "${ECR_REPO}:${IMAGE_TAG}" -f docker/Dockerfile .

echo "Tagging image..."
docker tag "${ECR_REPO}:${IMAGE_TAG}" "${ECR_URI}:${IMAGE_TAG}"

echo "Pushing image to ECR..."
docker push "${ECR_URI}:${IMAGE_TAG}"

echo "Updating ECS service..."
aws ecs update-service \
    --cluster "${ECS_CLUSTER}" \
    --service "${ECS_SERVICE}" \
    --force-new-deployment \
    --region "${AWS_REGION}"

echo "Deployment initiated. Waiting for service stability..."
aws ecs wait services-stable \
    --cluster "${ECS_CLUSTER}" \
    --services "${ECS_SERVICE}" \
    --region "${AWS_REGION}"

echo "Deployment complete!"
