# OIDC S3 Bucket: Regional Account Ownership

**Last Updated Date**: 2026-04-09
**Status**: Accepted

## Summary

The HyperShift OIDC S3 bucket and CloudFront distribution are provisioned as a single shared
resource per region in the regional cluster (RC) AWS account, owned by
`terraform/config/regional-cluster/`. All management clusters (MCs) in the region write to the
same bucket, with each hosted cluster's documents stored under a path prefix keyed by hosted
cluster ID (`/{hosted_cluster_id}/`). Cross-account write access is granted to any IAM principal
within the AWS Organization via `aws:PrincipalOrgID`, eliminating the need to update the bucket
policy as new MCs are provisioned.

## Context

- **Problem Statement**: The OIDC S3 bucket was initially provisioned in each management
  cluster's AWS account, giving each MC its own CloudFront URL. As the platform scales to
  multiple MCs per region, each MC's CloudFront domain becomes the OIDC issuer URL for all
  hosted clusters it runs. Migrating a hosted cluster between MCs would change its issuer URL,
  invalidating all workload identity tokens and requiring credential rotation across all workloads
  in the cluster. A stable, regional OIDC endpoint is required.
- **Constraints**: The HyperShift operator runs on the MC and must retain write access to the S3
  bucket. No cross-stack Terraform state references are permitted between RC and MC
  configurations. The MC pipeline must not require a cross-account provider alias.
- **Assumptions**: The MC provisioning pipeline already reads outputs from RC Terraform state
  (for the RHOBS API URL) before switching to the MC account context. The same pattern can carry
  OIDC bucket details to the MC Terraform.

## Decision

One shared S3 bucket + CloudFront distribution per region, provisioned by
`terraform/config/regional-cluster/` as part of RC infrastructure. The bucket is named
`hypershift-oidc-{regional_id}-{rc_account_id}`.

### Bucket policy: `aws:PrincipalOrgID`

The bucket policy allows any IAM principal in the AWS Organization to write OIDC documents.
No per-account statement updates are required when a new MC is added:

```json
{
  "Sid": "AllowHyperShiftOperatorOrgWrite",
  "Effect": "Allow",
  "Principal": { "AWS": "*" },
  "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
  "Resource": "arn:aws:s3:::hypershift-oidc-<regional_id>-<rc_account_id>/*",
  "Condition": {
    "StringEquals": { "aws:PrincipalOrgID": "<org_id>" }
  }
}
```

The HyperShift operator IAM role policy (in the MC account) still explicitly allows the same
S3 actions on the shared bucket ARN. Both policies must permit the action for cross-account
access to succeed (standard AWS cross-account dual-authorization model).

### How MC Terraform learns the bucket details

The MC provisioning pipeline (`provision-infra-mc.sh`) reads OIDC outputs from RC Terraform
state in the same step that reads the RHOBS API URL — before switching to the MC account:

```
provision-infra-mc.sh
  ├─ use_rc_account
  ├─ source read-iot-state.sh            # reads Maestro IoT cert/config from IoT state
  ├─ terraform init (regional-cluster state)
  ├─ terraform output oidc_bucket_name   → TF_VAR_oidc_bucket_name
  ├─ terraform output oidc_bucket_arn    → TF_VAR_oidc_bucket_arn
  ├─ terraform output oidc_bucket_region → TF_VAR_oidc_bucket_region
  ├─ terraform output oidc_cloudfront_domain → TF_VAR_oidc_cloudfront_domain
  ├─ use_mc_account
  └─ terraform apply management-cluster/
```

The IoT minting step (`iot-mint.sh`) creates only Maestro IoT certificates/policies;
OIDC bucket provisioning has been removed from the minting step entirely.

## Alternatives Considered

1. **Per-MC bucket in RC account (previous implementation)**: One bucket per MC, provisioned
   during the IoT minting step, with a per-account `aws:PrincipalAccount` bucket policy
   condition. Rejected because each MC gets a different CloudFront URL, making hosted cluster
   migration between MCs impossible without rotating workload credentials.

2. **Per-MC bucket in MC account**: Original approach. Rejected for the same reason, plus
   the additional concern that OIDC infrastructure logically belongs to the region, not to
   individual MCs.

3. **Provider alias in MC Terraform**: Add an `aws.regional` provider alias to MC Terraform
   that assumes a role in the RC account to create shared OIDC resources. Rejected because
   it widens MC Terraform's blast radius into the RC account on every apply.

4. **Dedicated OIDC writer role in RC account**: Create a single RC-account role that all MC
   HyperShift operators assume. Rejected: adds a hop without improving security, and the
   trust policy would need updating per MC.

5. **SSM Parameter Store for bucket details**: Write bucket details to SSM instead of reading
   RC Terraform outputs. Rejected: RC Terraform outputs are already authoritative; SSM would
   be an unsynchronised copy.

## Consequences

### Positive

- **Stable issuer URL** — The CloudFront domain never changes, regardless of which MC
  hosts a given control plane. Hosted cluster OIDC credentials survive MC migrations.
- **Zero-touch MC scaling** — New MC accounts automatically inherit write access via
  `aws:PrincipalOrgID`; no bucket policy update is needed.
- **Clean ownership** — OIDC bucket lifecycle is tied to the region, not individual MCs.
  `terraform destroy` on the regional cluster cleans up the shared OIDC endpoint.
- **No MC blast radius into RC** — MC Terraform never assumes a role in the RC account.

### Negative / Trade-offs

- **`aws:PrincipalOrgID` scope** — Any Organisation member account principal with appropriate
  IAM permissions can write to the bucket. The HyperShift operator role policy limits this in
  practice, but the bucket policy alone is less restrictive than a named-principal policy.
- **New required variable** — `org_id` is a new required input for `terraform/config/regional-cluster/`.
  Existing deploy configs must be updated before the next RC Terraform apply.
- **RC must be provisioned first** — The RC Terraform apply must complete before the first MC in
  a region can be provisioned (existing sequencing requirement, now also required for OIDC).

## Cross-Cutting Concerns

### Security

- Cross-account S3 access uses the dual-authorization model: both the MC IAM role policy and
  the RC bucket policy must permit the action.
- CloudFront OAC is the sole read path; the bucket blocks all public access.
- The HyperShift operator IAM role (MC account, EKS Pod Identity) is scoped to the minimum
  required S3 actions on the shared bucket ARN.

### Operability

- RC Terraform manages the full lifecycle of the shared bucket and CloudFront distribution.
- The MC deploy pipeline reads OIDC outputs from RC state using the existing pattern established
  for the RHOBS API URL, keeping the build spec structure consistent.
