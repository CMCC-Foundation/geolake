ARG REGISTRY=gtramonte
ARG TAG=latest
FROM $REGISTRY/geolake-drivers:$TAG

# Packages (datastore, workflow, dbmanager, geoquery, utils) + deps declared in pyproject.toml.
# Build from /code; installed into site-packages, sources removed (no more copy into /app).
COPY pyproject.toml /code/pyproject.toml
COPY datastore /code/datastore
COPY workflow  /code/workflow
COPY dbmanager /code/dbmanager
COPY geoquery  /code/geoquery
COPY utils     /code/utils
RUN pip install --no-cache-dir /code --break-system-packages && rm -rf /code

COPY ./wait-for-it.sh /
WORKDIR /
