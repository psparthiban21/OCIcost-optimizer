FROM container-registry.oracle.com/os/oraclelinux:9-slim

RUN microdnf install -y python3 python3-pip && \
    python3 -m pip install --no-cache-dir oci-cli && \
    microdnf clean all

WORKDIR /app
COPY apps/backend-api/src ./src
COPY apps/frontend ./frontend

ENV PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_MODE=mock \
    DATA_PROVIDER=mock \
    HOST=0.0.0.0 \
    PORT=8080 \
    STATIC_ROOT=/app/frontend \
    OCI_CLI_PATH=oci \
    OCI_CONFIG_FILE=/oci/config \
    OCI_PROFILE=DEFAULT

EXPOSE 8080
USER 10001

CMD ["python3", "-m", "oci_cost_optimizer"]
