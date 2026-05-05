# Ephemeral Environment Management

Manage ephemeral developer environments for the ROSA Regional Platform.

Parse the operation and options from: $ARGUMENTS

## Operations

| Operation | Description | Makefile target |
|-----------|-------------|-----------------|
| `provision` | Create a new ephemeral environment from a branch | `make ephemeral-provision` |
| `teardown` | Destroy an environment and clean up resources | `make ephemeral-teardown` |
| `resync` | Re-sync an environment to current branch state | `make ephemeral-resync` |
| `swap-branch` | Switch an environment to a different branch | `make ephemeral-swap-branch` |
| `list` | Display all tracked environments with status | `make ephemeral-list` |
| `e2e` | Run end-to-end tests against an environment | `make ephemeral-e2e` |
| `collect-logs` | Gather Kubernetes logs from RC/MC clusters | `make ephemeral-collect-logs` |
| `shell` | Open an interactive shell with credentials | `make ephemeral-shell` |
| `bastion-rc` | Connect to RC cluster bastion | `make ephemeral-bastion-rc` |
| `bastion-mc` | Connect to MC cluster bastion | `make ephemeral-bastion-mc` |
| `port-forward-rc` | Tunnel RC cluster services | `make ephemeral-port-forward-rc` |
| `port-forward-mc` | Tunnel MC cluster services | `make ephemeral-port-forward-mc` |

## Parsing $ARGUMENTS

Extract:
- **operation** — one of the operations above (required)
- **ID** — environment identifier, if provided
- **BRANCH** — git branch name, if provided
- **CLUSTER** — `rc` or `mc`, if provided (for collect-logs)
- **--all** flag — for port-forward operations

## Execution

Run the appropriate `make` target with the extracted parameters. Pass Make variables as `KEY=value` arguments.

Examples:
```bash
make ephemeral-provision ID=my-env BRANCH=feature/my-feature
make ephemeral-teardown ID=my-env
make ephemeral-resync ID=my-env
make ephemeral-swap-branch ID=my-env BRANCH=main
make ephemeral-list
make ephemeral-e2e ID=my-env
make ephemeral-collect-logs ID=my-env CLUSTER=rc
```

## After running

- For `list`: display the output in a readable table
- For `provision`: confirm the environment ID and report its status
- For `e2e`: summarize pass/fail counts from the test output
- For `collect-logs`: report where the logs were saved

## Error handling

If `make` exits non-zero, display the error output and suggest:
1. Check that AWS credentials are available (`aws sts get-caller-identity --profile central`)
2. Check that the environment ID exists (`/ephemeral list`)
3. Check network connectivity to the ephemeral environment
