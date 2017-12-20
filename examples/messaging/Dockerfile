FROM python:3

ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH /usr/src/messaging-app
ENV DJANGO_SETTINGS_MODULE messagingapp.settings
EXPOSE 80
ENTRYPOINT ["/docker-entrypoint.sh"]

COPY requirements.txt /usr/src/messaging-app/requirements.txt
RUN ["pip", "install", "-r", "/usr/src/messaging-app/requirements.txt"]

COPY docker-entrypoint.sh /docker-entrypoint.sh

COPY messagingapp /usr/src/messaging-app/messagingapp
