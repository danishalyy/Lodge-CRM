# Keep the pinned server release and /data format; use a maintained compiler and
# Debian security-supported base. No legacy MinIO binary download is required.
FROM golang:1.27-bookworm AS builder
ARG MINIO_VERSION=RELEASE.2025-10-15T17-29-55Z
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi \
 && mkdir -p /out \
 && GOBIN=/out CGO_ENABLED=0 go install github.com/minio/minio@${MINIO_VERSION} \
 && /out/minio --version

FROM debian:bookworm-slim
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi \
 && apt-get -o Acquire::http::Proxy="${http_proxy:-${HTTP_PROXY:-}}" update \
 && apt-get -o Acquire::http::Proxy="${http_proxy:-${HTTP_PROXY:-}}" install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /out/minio /usr/local/bin/minio
EXPOSE 9000 9001
ENTRYPOINT ["/usr/local/bin/minio"]
CMD ["server", "/data", "--console-address", ":9001"]
