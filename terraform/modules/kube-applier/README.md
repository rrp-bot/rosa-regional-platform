# kube-applier Module

Creates IAM resources for the `kube-applier-aws` controller on a Management Cluster.

## Overview

The `kube-applier-aws` controller reads desire documents from DynamoDB tables in the
Regional Cluster (RC) account and applies them to the local Management Cluster Kubernetes
API. It uses EKS Pod Identity to obtain cross-account IAM credentials.

## IAM Permissions

**Specs tables** (`{mc_name}-specs-*` in RC account) — read-only + DynamoDB Streams:
- `dynamodb:GetItem`, `dynamodb:Scan`, `dynamodb:Query`
- `dynamodb:DescribeStream`, `dynamodb:GetRecords`, `dynamodb:GetShardIterator`, `dynamodb:ListStreams`

**Status tables** (`{mc_name}-status-*` in RC account) — read-write:
- `dynamodb:GetItem`, `dynamodb:Scan`, `dynamodb:PutItem`, `dynamodb:DeleteItem`

## Usage

```hcl
module "kube_applier" {
  source = "../../modules/kube-applier"

  management_id    = var.management_id
  eks_cluster_name = module.management_cluster.cluster_name
  rc_aws_account_id = var.regional_aws_account_id
  aws_region       = var.region
}
```

## DynamoDB Tables

Tables are created separately in the RC account via the `kube-applier-dynamodb-provisioning`
Terraform config (analogous to `maestro-agent-iot-provisioning`). Six tables are created per MC:

- `{mc_name}-specs-applydesires`
- `{mc_name}-specs-deletedesires`
- `{mc_name}-specs-readdesires`
- `{mc_name}-status-applydesires`
- `{mc_name}-status-deletedesires`
- `{mc_name}-status-readdesires`
