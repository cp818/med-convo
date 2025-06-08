#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status

# Configuration
PROJECT_ID=$(gcloud config get-value project)
SERVICE_NAME=livekit-token-server
REGION=us-central1

# Build the Docker image
echo "Building Docker image..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME .

# Deploy to Cloud Run with secrets from Secret Manager
echo "Deploying to Cloud Run with secrets..."
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --update-secrets=LIVEKIT_API_KEY=LIVEKIT_API_KEY:latest,LIVEKIT_SECRET=LIVEKIT_SECRET:latest

# Output the service URL
echo "Deployment complete!"
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)')
echo "Service URL: $SERVICE_URL"
echo "Test the health endpoint: curl $SERVICE_URL/health"
