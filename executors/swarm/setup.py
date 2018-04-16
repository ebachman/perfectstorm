from setuptools import setup

setup(
    name='perfectstorm-executors-swarm',
    version='0.1',
    scripts=['storm-swarm'],
    install_requires=[
        'perfectstorm-lib',
    ],
)
