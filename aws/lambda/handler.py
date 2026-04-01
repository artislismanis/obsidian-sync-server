"""AWS Lambda handler using Mangum to wrap the FastAPI application.

This is used in the Lambda + Fargate hybrid architecture:
- Lambda (this handler) serves all REST API requests via API Gateway
- Fargate serves WebSocket connections via ALB (separate service)
"""

from mangum import Mangum

from obsidian_sync.main import app

handler = Mangum(app, lifespan="off")
