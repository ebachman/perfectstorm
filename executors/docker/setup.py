from setuptools import setup, find_packages

setup(
    name='perfectstorm-executors-docker',
    version='0.1',
    scripts=['storm-docker'],
    install_requires=[
        'perfectstorm-lib',
    ],
    dependency_links=[
        '../../library',
    ],
)

