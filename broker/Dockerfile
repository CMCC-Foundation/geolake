FROM rg.nl-ams.scw.cloud/geokube-production/geodds-datastore:latest
ARG GEODDS_UTILS_PAT
WORKDIR /app
COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir -r /code/requirements.txt
RUN pip install git+https://opengeokube:${GEODDS_UTILS_PAT}@github.com/opengeokube/geodds-utils.git
COPY app /app
CMD [ "python", "main.py" ]
