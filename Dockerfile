# syntax=docker/dockerfile:1

FROM rust:bookworm AS builder
WORKDIR /app

COPY rust-toolchain.toml Cargo.toml Cargo.lock ./
COPY src ./src

ENV CARGO_REGISTRIES_CRATES_IO_PROTOCOL=sparse
RUN cargo build --release

FROM debian:bookworm-slim AS runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/zeppelinker /usr/local/bin/zeppelinker
USER nobody
CMD ["/usr/local/bin/zeppelinker"]
