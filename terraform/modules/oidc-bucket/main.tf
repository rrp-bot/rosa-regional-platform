# =============================================================================
# OIDC Bucket Module
#
# Creates the shared regional S3 bucket and CloudFront distribution for
# HyperShift OIDC discovery documents. ONE bucket per region, shared by all
# management clusters in the region.
#
# Each hosted cluster's OIDC documents are stored under a path prefix:
#   /{hosted_cluster_id}/.well-known/openid-configuration
#   /{hosted_cluster_id}/keys.json
#
# The HyperShift operator (running in any management cluster within the AWS
# Organization) writes OIDC documents cross-account via the bucket policy grant.
# No per-MC policy updates are required when new management clusters are added.
# =============================================================================

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  bucket_name = "hypershift-oidc-${var.regional_id}-${data.aws_caller_identity.current.account_id}"

  common_tags = merge(
    var.tags,
    {
      Component = "hypershift-oidc"
      Region    = data.aws_region.current.id
      ManagedBy = "terraform"
    }
  )
}
