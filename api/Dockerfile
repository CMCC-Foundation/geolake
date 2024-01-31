<<<<<<< HEAD
ARG REGISTRY=rg.nl-ams.scw.cloud/geogeolake-production
=======
ARG REGISTRY=rg.fr-par.scw.cloud/geolake
>>>>>>> release_0.1.1
ARG TAG=latest
FROM $REGISTRY/geolake-datastore:$TAG
WORKDIR /app
COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY app /app
EXPOSE 80
CMD ["uvicorn", "app.main:app", "--proxy-headers", "--host", "0.0.0.0", "--port", "80"]
