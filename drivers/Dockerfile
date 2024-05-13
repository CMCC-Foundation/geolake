ARG REGISTRY=rg.fr-par.scw.cloud/geokube
# ARG TAG=v0.2.6b1
ARG TAG=latest
FROM $REGISTRY/geokube:$TAG

COPY dist/intake_geokube-0.1a0-py3-none-any.whl /

RUN pip3.10 install /intake_geokube-0.1a0-py3-none-any.whl
RUN rm /intake_geokube-0.1a0-py3-none-any.whl
