FROM perfectstorm/perfectstorm-lib:latest

ENV PYTHONUNBUFFERED 1
ENV STORM_BIND 0.0.0.0

ENTRYPOINT ["/docker-entrypoint.sh"]

EXPOSE 8000

COPY docker-entrypoint.sh /

COPY cli /usr/src/perfectstorm/cli
COPY core /usr/src/perfectstorm/core

RUN ["pip", "install", "/usr/src/perfectstorm/cli"]
RUN ["pip", "install", "/usr/src/perfectstorm/core"]
