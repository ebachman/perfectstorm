from setuptools import setup

setup(
    name='perfectstorm-executors-loadbalancer',
    version='0.1',
    scripts=['storm-loadbalancer'],
    install_requires=[
        'perfectstorm-lib',
    ],
    dependency_links=[
        '../../library',
    ],
)
