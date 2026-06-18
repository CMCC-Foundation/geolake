ARG REGISTRY=gtramonte
ARG TAG=latest
FROM $REGISTRY/geolake-drivers:$TAG

# Pacchetti (datastore, workflow, dbmanager, geoquery, utils) + deps dichiarati in pyproject.toml.
# Build da /code; installati in site-packages, sorgenti rimossi (niente più copia in /app).
COPY pyproject.toml /code/pyproject.toml
COPY datastore /code/datastore
COPY workflow  /code/workflow
COPY dbmanager /code/dbmanager
COPY geoquery  /code/geoquery
COPY utils     /code/utils
RUN pip install --no-cache-dir /code --break-system-packages && rm -rf /code

COPY ./wait-for-it.sh /
WORKDIR /
