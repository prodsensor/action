FROM python:3.11-slim

LABEL maintainer="ProdSensor <support@prodsensor.com>"
LABEL org.opencontainers.image.source="https://github.com/prodsensor/action"
LABEL org.opencontainers.image.description="ProdSensor GitHub Action for production readiness analysis"

# Install dependencies
RUN pip install --no-cache-dir \
    httpx>=0.24.0 \
    click>=8.0.0 \
    rich>=13.0.0 \
    pydantic>=2.0.0

# Copy action code
COPY src/ /action/
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
