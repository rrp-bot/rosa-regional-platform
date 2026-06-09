IMAGE_REPO ?= quay.io/slopezz/zoa-tools
IMAGE_TAG ?= latest
GIT_SHA := $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
CONTAINER_RUNTIME ?= $(shell command -v podman 2>/dev/null || echo docker)

.PHONY: build push

build:
	$(CONTAINER_RUNTIME) build --platform linux/amd64 -t $(IMAGE_REPO):$(IMAGE_TAG) -t $(IMAGE_REPO):$(GIT_SHA) .

push: build
	$(CONTAINER_RUNTIME) push $(IMAGE_REPO):$(IMAGE_TAG)
	$(CONTAINER_RUNTIME) push $(IMAGE_REPO):$(GIT_SHA)
