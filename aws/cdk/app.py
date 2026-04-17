"""AWS CDK application for Obsidian Sync Server SaaS deployment.

Instantiates all infrastructure stacks: network, database, compute, storage, and CDN.
See aws/README.md for architecture overview.
"""

import aws_cdk as cdk

from stacks.cdn import CdnStack
from stacks.compute import ComputeStack
from stacks.database import DatabaseStack
from stacks.network import NetworkStack
from stacks.storage import StorageStack

app = cdk.App()

# Foundation: VPC with public + private subnets
network = NetworkStack(app, "ObsidianSyncNetwork")

# Database: Aurora Serverless V2 PostgreSQL
database = DatabaseStack(
    app,
    "ObsidianSyncDatabase",
    vpc=network.vpc,
)

# Storage: S3 buckets for vault data and portal assets
storage = StorageStack(app, "ObsidianSyncStorage")

# Compute: ECS Fargate behind ALB
compute = ComputeStack(
    app,
    "ObsidianSyncCompute",
    vpc=network.vpc,
    db_cluster=database.cluster,
    db_security_group=database.db_security_group,
)

# CDN: CloudFront distribution (portal S3 + API ALB)
cdn = CdnStack(
    app,
    "ObsidianSyncCdn",
    portal_bucket=storage.portal_bucket,
    alb=compute.alb,
)

app.synth()
