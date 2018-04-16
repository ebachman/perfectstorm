from setuptools import setup, find_packages

setup(
    name='perfectstorm-core',
    version='0.1',
    packages=find_packages(),
    scripts=['stormd'],
    install_requires=[
        'blinker >= 1.4, < 1.5',
        'django >= 1.11, < 1.12',
        'django-rest-framework-mongoengine >= 3.3, < 3.4',
        'djangorestframework >= 3.8, < 3.9',
        'gevent >= 1.2, < 1.3',
        'greenlet >= 0.4, < 0.5',
        'gunicorn >= 19, < 20',
        'mongoengine >= 0.15, < 0.16',
        'pymongo >= 3.6, < 3.7',
    ],
    zip_safe=False,
)
