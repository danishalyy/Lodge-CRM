# Build MinIO from a pinned upstream source release.
# This avoids relying on legacy pre-built binary URLs and works natively on
# both linux/amd64 and linux/arm64 (including Apple Silicon via Docker Desktop).
FROM golang:1.24.8-alpine AS builder

RUN apk add --no-cache ca-certificates git

ARG MINIO_VERSION=RELEASE.2025-10-15T17-29-55Z
RUN mkdir -p /out && \
    GOBIN=/out CGO_ENABLED=0 go install github.com/minio/minio@${MINIO_VERSION} && \
    /out/minio --version

FROM alpine:3.21
RUN apk add --no-cache ca-certificates curl

COPY --from=builder /out/minio /usr/local/bin/minio

EXPOSE 9000 9001
ENTRYPOINT ["/usr/local/bin/minio"]
CMD ["server", "/data", "--console-address", ":9001"]
