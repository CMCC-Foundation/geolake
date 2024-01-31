ARG REGISTRY=rg.nl-ams.scw.cloud/geogeolake-production
ARG TAG=latest
ARG SENTINEL_USERNAME=...
ARG SENTINEL_PASSWORD=...
FROM $REGISTRY/geolake-datastore:$TAG
WORKDIR /app
ENV SENTINEL_USERNAME=$SENTINEL_USERNAME
ENV SENTINEL_PASSWORD=$SENTINEL_PASSWORD
COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir -r /code/requirements.txt
COPY app /app
CMD [ "python", "main.py" ]
