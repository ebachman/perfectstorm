"""
Django settings for stormcore project.

Generated by 'django-admin startproject' using Django 1.11.7.

For more information on this file, see
https://docs.djangoproject.com/en/1.11/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.11/ref/settings/
"""

import os

import mongoengine

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEBUG = bool(os.environ.get('STORM_DEBUG'))

# Secret key: this is disabled as we are not using any feature requiring
# cryptographic signing.
# https://docs.djangoproject.com/en/1.11/ref/settings/#secret-key
SECRET_KEY = 'x'

# Allowed hosts: we allow everything. Security might be provided using
# TLS authentication.
# https://docs.djangoproject.com/en/1.11/ref/settings/#allowed-hosts
ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_mongoengine',
    'stormcore.apiserver.apps.ApiServerConfig',
    'stormcore.ui.apps.UIConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'stormcore.middleware.RequestLogMiddleware',
]

ROOT_URLCONF = 'stormcore.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
            ],
        },
    },
]

WSGI_APPLICATION = 'stormcore.wsgi.application'


# Logging
# https://docs.djangoproject.com/en/2.0/ref/settings/#logging

# Disable Django logging (it is set up by stormd)
LOGGING_CONFIG = None


# Database
# https://docs.djangoproject.com/en/1.11/ref/settings/#databases

DATABASES = {}


# Internationalization
# https://docs.djangoproject.com/en/1.11/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = False

USE_L10N = False

USE_TZ = False


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.11/howto/static-files/

STATIC_URL = '/static/'

STATIC_ROOT = os.path.join(BASE_DIR, 'static')


# Rest Framework
# http://www.django-rest-framework.org/api-guide/settings/

REST_FRAMEWORK = {
    # Disable authentication
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [],
    'UNAUTHENTICATED_USER': None,
    # Disable interpretation of '.json' in URLs. This causes problems
    # when resource IDs or names contain dots
    'FORMAT_SUFFIX_KWARG': None,
}


# MongoDB
# http://docs.mongoengine.org/guide/connecting.html

DEFAULT_MONGODB_URI = 'mongodb://127.0.0.1/perfectstorm'
MONGODB_URI = os.environ.get('STORM_MONGO') or DEFAULT_MONGODB_URI

mongoengine.connect(host=MONGODB_URI, connect=False)
