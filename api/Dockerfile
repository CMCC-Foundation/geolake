ARG REGISTRY=rg.nl-ams.scw.cloud/geodds-production
ARG TAG=latest
ARG GEODDS_UTILS_PAT
FROM $REGISTRY/geolake-datastore:$TAG
WORKDIR /app
COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
RUN pip install git+https://opengeokube:${GEODDS_UTILS_PAT}@github.com/opengeokube/geodds-utils.git
COPY app /app
EXPOSE 80
CMD ["uvicorn", "app.main:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "80"]
