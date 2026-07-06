ARG REGISTRY=gtramonte
ARG TAG=latest
FROM $REGISTRY/geolake-datastore:$TAG

# Code + deps declared in pyproject.toml; installed in site-packages, sources removed.
# The executor stays ROOT with an RW filesystem: in production it writes to /downloads (hardening deferred).
WORKDIR /app
COPY pyproject.toml /code/pyproject.toml
COPY app /code/app
RUN pip install --no-cache-dir /code --break-system-packages && rm -rf /code

CMD ["python", "-m", "main"]
