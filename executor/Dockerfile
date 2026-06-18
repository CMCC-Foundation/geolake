ARG REGISTRY=gtramonte
ARG TAG=latest
FROM $REGISTRY/geolake-datastore:$TAG

# Codice + deps dichiarati in pyproject.toml; installati in site-packages, sorgenti rimossi.
# L'executor resta ROOT con filesystem RW: in produzione scrive su /downloads (hardening deferito).
WORKDIR /app
COPY pyproject.toml /code/pyproject.toml
COPY app /code/app
RUN pip install --no-cache-dir /code --break-system-packages && rm -rf /code

CMD ["python", "-m", "main"]
