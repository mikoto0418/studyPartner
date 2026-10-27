FROM criyle/go-judge:v1.12.2 AS sandbox
FROM debian:bookworm-slim
ARG DEBIAN_MIRROR=http://deb.debian.org
RUN sed -i "s|http://deb.debian.org|${DEBIAN_MIRROR}|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=3 update && apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
    gcc g++ libc6-dev python3 openjdk-17-jdk-headless nodejs ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=sandbox /opt/go-judge /opt/go-judge
COPY --from=sandbox /opt/mount.yaml /opt/mount.yaml
RUN sed -i 's/java-21-openjdk/java-17-openjdk/g' /opt/mount.yaml
WORKDIR /opt
ENTRYPOINT ["/opt/go-judge"]
CMD ["-http-addr", ":5050", "-parallelism", "4", "-file-timeout", "10m"]
