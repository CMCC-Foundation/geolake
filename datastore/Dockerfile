ARG REGISTRY=rg.fr-par.scw.cloud/geolake
ARG TAG=latest
FROM $REGISTRY/geolake-drivers:$TAG
RUN conda install -c conda-forge --yes --freeze-installed psycopg2 \
    && conda clean -afy
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt    
COPY ./datastore /app/datastore
COPY ./workflow /app/workflow
COPY ./dbmanager /app/dbmanager
COPY ./utils /app/utils
COPY ./tests /app/tests
COPY ./wait-for-it.sh /

