ARG REGISTRY=rg.nl-ams.scw.cloud/geokube-production
ARG TAG=latest
FROM $REGISTRY/geokube:$TAG
RUN conda install -c conda-forge --yes --freeze-installed intake=0.6.6
RUN conda clean -afy
COPY dist/geolake_drivers-1.0b0-py3-none-any.whl /
RUN pip install /geolake_drivers-1.0b0-py3-none-any.whl
RUN rm /geolake_drivers-1.0b0-py3-none-any.whl
