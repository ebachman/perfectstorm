from setuptools import setup, find_packages

setup(
    name='perfectstorm-lib',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'requests >= 2.13, < 3',
    ],
    extras_require={
        'gevent': ['gevent >= 1.2, < 1.3'],
    },
)
