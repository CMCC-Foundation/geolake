ARG REGISTRY=rg.fr-par.scw.cloud/geolake
ARG TAG=latest
FROM geolake-drivers:$TAG

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt    
COPY ./datastore /app/datastore
COPY ./workflow /app/workflow
COPY ./dbmanager /app/dbmanager
COPY ./geoquery /app/geoquery
COPY ./utils /app/utils
COPY ./tests /app/tests
COPY ./wait-for-it.sh /

