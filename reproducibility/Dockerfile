FROM ubuntu@sha256:678c6550cc43645e08669028bc177f50be4e7c5b8cca677067b1914d4afc7a03

ARG TARGETARCH
RUN test "${TARGETARCH}" = "amd64"

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        7zip=23.01+dfsg-11 \
        brotli=1.1.0-2build2 \
        bzip2=1.0.8-5.1build0.1 \
        ca-certificates=20260601~24.04.1 \
        coreutils=9.4-3ubuntu6.2 \
        curl=8.5.0-2ubuntu10.11 \
        gzip=1.12-1ubuntu3.2 \
        lz4=1.9.4-1build1.1 \
        python3=3.12.3-0ubuntu2.1 \
        time=1.9-0.2build1 \
        unzip=6.0-28ubuntu4.1 \
        xz-utils=5.6.1+really5.4.5-1ubuntu0.3 \
        zstd=1.5.5+dfsg2-2build1.1 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin reproducer
WORKDIR /opt/cubr-repro
COPY --chown=reproducer:reproducer . /opt/cubr-repro/
RUN chmod 0555 acquire.sh entrypoint.sh \
    && chmod 0444 assets/manifest.txt archiver_templates.json corpus_manifest.tsv \
        expected_aggregates.json expected_cells.json packages.lock

USER reproducer
VOLUME ["/workspace"]
ENTRYPOINT ["/opt/cubr-repro/entrypoint.sh"]
