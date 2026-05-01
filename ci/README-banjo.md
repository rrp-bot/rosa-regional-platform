# Building CI Container in Banjo Environment

The Banjo environment requires special build arguments to work with the corporate proxy and CA certificates.

## Prerequisites

- Proxy CA certificate mounted at: `/etc/pki/ca-trust/source/anchors/proxy-ca.crt`
- Proxy environment variables must be set (check your shell environment for `HTTP_PROXY`, `HTTPS_PROXY`, etc.)

## Build Command

```bash
cd /workspace/rosa-regional-platform && podman build \
  --network=host \
  --layers=false \
  --build-arg HTTP_PROXY=$HTTP_PROXY \
  --build-arg HTTPS_PROXY=$HTTPS_PROXY \
  --build-arg http_proxy=$http_proxy \
  --build-arg https_proxy=$https_proxy \
  --volume /etc/pki/ca-trust/source/anchors/proxy-ca.crt:/etc/pki/ca-trust/source/anchors/proxy-ca.crt:ro \
  -t rosa-regional-platform-ci:latest \
  -f ci/Containerfile .
```

## Build Arguments Explained

- `--network=host` - Uses host networking so containers can access the proxy
- `--layers=false` - Disables layer caching to ensure `update-ca-trust` runs with the mounted certificate
- `--build-arg HTTP_PROXY=...` - Passes proxy environment variables into the build for dnf, curl, etc.
- `--volume /etc/pki/ca-trust/source/anchors/proxy-ca.crt:...` - Mounts the proxy CA certificate into the container during build

## Proxy Allowlist Requirements

The following domains must be allowed through the proxy:

- `cdn-ubi.redhat.com` - Red Hat UBI packages
- `releases.hashicorp.com` - Terraform installation
- `rpm.releases.hashicorp.com` - HashiCorp RHEL repository
- `get.helm.sh` - Helm binary downloads
- `raw.githubusercontent.com` - Helm install script
- `astral.sh` - uv Python package manager installer
- `awscli.amazonaws.com` - AWS CLI downloads
- `github.com` - yq and k6 downloads
- `pypi.org` - Python packages (awscurl)

## Containerfile Changes for Banjo

The `ci/Containerfile` includes the following modifications for proxy environments:

1. **CA Trust Update**: Runs `update-ca-trust` to pick up mounted proxy CA certificate
2. **Terraform via Repo**: Uses HashiCorp's RHEL repository instead of manual GPG verification (avoids keyserver blocking)
3. **Native TLS for uv**: Added `--native-tls` flag to use system CA certificates instead of Rust's built-in TLS

## Verification

After a successful build, verify the image:

```bash
podman images | grep rosa-regional-platform-ci
```

Expected output:
```
localhost/rosa-regional-platform-ci  latest      <image-id>  <time>  ~1.45 GB
```
