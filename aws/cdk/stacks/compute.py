"""Compute stack: ECS Fargate service behind an ALB."""

from aws_cdk import Duration, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_ecs_patterns as ecs_patterns
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_rds as rds
from constructs import Construct


class ComputeStack(Stack):
    """ECS Fargate service with ALB.

    Task definition: 0.5 vCPU, 1 GB memory.
    ALB idle timeout set to 4000 seconds for WebSocket support.
    Health check on /api/v1/health.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        db_cluster: rds.IDatabaseCluster,
        db_security_group: ec2.ISecurityGroup,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ECS Cluster
        cluster = ecs.Cluster(
            self,
            "ObsidianSyncCluster",
            vpc=vpc,
        )

        # Fargate service behind ALB
        self.fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "ObsidianSyncService",
            cluster=cluster,
            cpu=512,  # 0.5 vCPU
            memory_limit_mib=1024,  # 1 GB
            desired_count=1,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_asset("../../server"),
                container_port=8000,
                environment={
                    "DEPLOYMENT_MODE": "saas",
                    "DATABASE_URL": f"postgresql+asyncpg://"
                    f"{db_cluster.secret.secret_value_from_json('username').unsafe_unwrap()}"
                    f":{db_cluster.secret.secret_value_from_json('password').unsafe_unwrap()}"
                    f"@{db_cluster.cluster_endpoint.hostname}"
                    f":5432/obsidian_sync",
                },
            ),
            public_load_balancer=True,
        )

        # Set ALB idle timeout to 4000s for WebSocket support
        self.fargate_service.load_balancer.set_attribute(
            "idle_timeout.timeout_seconds", "4000"
        )

        # Health check configuration
        self.fargate_service.target_group.configure_health_check(
            path="/api/v1/health",
            healthy_http_codes="200",
            interval=Duration.seconds(30),
            timeout=Duration.seconds(10),
            healthy_threshold_count=2,
            unhealthy_threshold_count=3,
        )

        # Allow Fargate tasks to connect to Aurora
        db_security_group.add_ingress_rule(
            peer=self.fargate_service.service.connections.security_groups[0],
            connection=ec2.Port.tcp(5432),
            description="Allow Fargate tasks to connect to Aurora",
        )

        # Expose ALB for CDN origin
        self.alb = self.fargate_service.load_balancer
