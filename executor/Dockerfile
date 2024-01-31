ARG REGISTRY=rg.nl-ams.scw.cloud/geodds-production
ARG TAG=latest
ARG SENTINEL_USERNAME=...
ARG SENTINEL_PASSWORD=...
ARG GEODDS_UTILS_PAT
FROM $REGISTRY/geolake-datastore:$TAG
WORKDIR /app
ENV SENTINEL_USERNAME=$SENTINEL_USERNAME
ENV SENTINEL_PASSWORD=$SENTINEL_PASSWORD
COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir -r /code/requirements.txt
RUN pip install -force-reinstall git+https://opengeokube:${GEODDS_UTILS_PAT}@github.com/opengeokube/geodds-utils.git
COPY app /app
CMD [ "python", "main.py" ]
