"""Database stack: Aurora Serverless V2 PostgreSQL cluster."""

from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_rds as rds
from constructs import Construct


class DatabaseStack(Stack):
    """Aurora Serverless V2 PostgreSQL cluster with a security group
    that allows inbound access from the Fargate service."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Security group for the Aurora cluster
        self.db_security_group = ec2.SecurityGroup(
            self,
            "DbSecurityGroup",
            vpc=vpc,
            description="Allow access from Fargate tasks to Aurora",
            allow_all_outbound=True,
        )

        # Aurora Serverless V2 cluster
        self.cluster = rds.DatabaseCluster(
            self,
            "ObsidianSyncDb",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_15_4,
            ),
            serverless_v2_min_capacity=0.5,
            serverless_v2_max_capacity=4,
            writer=rds.ClusterInstance.serverless_v2("Writer"),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
            security_groups=[self.db_security_group],
            default_database_name="obsidian_sync",
            removal_policy=RemovalPolicy.SNAPSHOT,
        )
