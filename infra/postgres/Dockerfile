# Keep the existing PostgreSQL major version, Alpine base and data directory.
FROM postgres:16-alpine AS vector-build
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then cat /run/secrets/build_ca >> /etc/ssl/cert.pem; fi \
 && apk add --no-cache build-base curl
WORKDIR /tmp/vector
RUN curl -fsSL https://codeload.github.com/pgvector/pgvector/tar.gz/refs/tags/v0.8.2 -o vector.tar.gz \
 && echo '69f4019389af05dc1c9548deb8628e62878e6e207c03907f2b8af2016472cdaa  vector.tar.gz' | sha256sum -c - \
 && tar xzf vector.tar.gz --strip-components=1 \
 && make OPTFLAGS='' with_llvm=no \
 && make install with_llvm=no DESTDIR=/opt/vector
FROM postgres:16-alpine
COPY --from=vector-build /opt/vector/ /
