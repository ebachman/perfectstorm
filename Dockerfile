FROM python:3.6

ENV PYTHONUNBUFFERED 1
ENV DJANGO_SETTINGS_MODULE teacup.settings

WORKDIR /usr/src/perfectstorm/

ENTRYPOINT ["/docker-entrypoint.sh"]

EXPOSE 8000

COPY docker-entrypoint.sh /

COPY cli /usr/src/perfectstorm/cli
COPY core /usr/src/perfectstorm/core
COPY executors /usr/src/perfectstorm/executors
COPY lib /usr/src/perfectstorm/lib

RUN ["pip", "install", "/usr/src/perfectstorm/core"]
RUN ["pip", "install", "/usr/src/perfectstorm/lib"]
RUN ["pip", "install", "/usr/src/perfectstorm/cli"]
RUN ["pip", "install", "/usr/src/perfectstorm/executors/consul"]
RUN ["pip", "install", "/usr/src/perfectstorm/executors/docker"]
RUN ["pip", "install", "/usr/src/perfectstorm/executors/loadbalancer"]

RUN ["stormd", "--bootstrap-only"]
