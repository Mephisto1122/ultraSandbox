# ultra-sandbox/python
FROM python:3.12-slim-bookworm
RUN useradd -m sandbox && mkdir -p /work && chown sandbox /work
USER sandbox
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PATH="/home/sandbox/.local/bin:$PATH"
RUN pip install --user -q pytest
WORKDIR /work
