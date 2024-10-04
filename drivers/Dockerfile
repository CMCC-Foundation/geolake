ARG REGISTRY=rg.fr-par.scw.cloud/geokube
#ARG TAG=v0.2.6b2
#ARG TAG=2024.05.03.10.36
ARG TAG=v0.2.7
FROM $REGISTRY/geokube:$TAG

COPY dist/intake_geokube-0.1a0-py3-none-any.whl /
RUN pip install /intake_geokube-0.1a0-py3-none-any.whl --break-system-packages
RUN rm /intake_geokube-0.1a0-py3-none-any.whl