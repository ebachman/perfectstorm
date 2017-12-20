from setuptools import setup, find_packages

setup(
    name='perfectstorm-executors-consul',
    version='0.1',
    scripts=['storm-consul'],
    install_requires=[
        'perfectstorm-lib',
    ],
    dependency_links=[
        '../../library',
    ],
)
