ARG REGISTRY=gtramonte
ARG TAG=latest
FROM $REGISTRY/geolake-datastore:$TAG

# All code (API + geolake-datastore base packages) is now in site-packages → no PYTHONPATH needed.
# DONTWRITEBYTECODE + HOME=/tmp: for the read-only rootfs (Python won't write .pyc, ~/.cache on tmpfs).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp

WORKDIR /app

COPY pyproject.toml /code/pyproject.toml
COPY app /code/app
RUN pip install --no-cache-dir /code --break-system-packages && rm -rf /code

RUN groupadd --gid 10001 appuser && useradd --uid 10001 --gid 10001 --no-create-home appuser
USER appuser

EXPOSE 8080
CMD ["uvicorn", "main:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "8080"]
