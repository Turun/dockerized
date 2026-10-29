FROM python:3.12-slim

COPY pushgateway_lite.py /app/pushgateway_lite.py

# Store is in-memory; run as non-root for good measure.
# 9091 matches the official pushgateway's default port (caddy proxy unchanged).
EXPOSE 9091
USER nobody
CMD ["python3", "/app/pushgateway_lite.py", "9091"]
