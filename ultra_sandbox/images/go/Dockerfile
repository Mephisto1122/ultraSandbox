# ultra-sandbox/go
FROM golang:1.24-bookworm
RUN useradd -m sandbox && mkdir -p /work && chown sandbox /work
USER sandbox
ENV GOFLAGS=-buildvcs=false GOPATH=/home/sandbox/go
WORKDIR /work
