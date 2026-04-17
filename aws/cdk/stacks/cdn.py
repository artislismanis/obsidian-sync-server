"""CDN stack: CloudFront distribution for portal (S3) and API (ALB)."""

from aws_cdk import Duration, Stack
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_s3 as s3
from constructs import Construct


class CdnStack(Stack):
    """CloudFront distribution with two origins:
    - S3 for portal static assets (default behavior)
    - ALB for API requests (/api/*)
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        portal_bucket: s3.IBucket,
        alb: elbv2.IApplicationLoadBalancer,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Origin Access Identity for S3
        oai = cloudfront.OriginAccessIdentity(
            self,
            "PortalOAI",
            comment="OAI for Obsidian Sync portal assets",
        )
        portal_bucket.grant_read(oai)

        # S3 origin for portal static assets
        s3_origin = origins.S3Origin(
            portal_bucket,
            origin_access_identity=oai,
        )

        # ALB origin for API
        alb_origin = origins.HttpOrigin(
            alb.load_balancer_dns_name,
            protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY,
            http_port=80,
            keepalive_timeout=Duration.seconds(60),
            read_timeout=Duration.seconds(60),
        )

        # CloudFront distribution
        self.distribution = cloudfront.Distribution(
            self,
            "ObsidianSyncDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=s3_origin,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
            ),
            additional_behaviors={
                "/api/*": cloudfront.BehaviorOptions(
                    origin=alb_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER,
                ),
            },
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_page_path="/index.html",
                    response_http_status=200,
                    ttl=Duration.seconds(0),
                ),
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_page_path="/index.html",
                    response_http_status=200,
                    ttl=Duration.seconds(0),
                ),
            ],
        )
