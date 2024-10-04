ARG REGISTRY=rg.fr-par.scw.cloud/geolake
ARG TAG=latest
FROM $REGISTRY/geolake-drivers:$TAG

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt --break-system-packages
COPY ./datastore /app/datastore
COPY ./workflow /app/workflow
COPY ./dbmanager /app/dbmanager
COPY ./geoquery /app/geoquery
COPY ./utils /app/utils
COPY ./tests /app/tests
COPY ./wait-for-it.sh /

WORKDIR /