from setuptools import setup, find_packages

setup(
    name='perfectstorm-executors-swarm',
    version='0.1',
    packages=find_packages(),
    scripts=[
        'storm-swarm-discovery',
        'storm-swarm-labeling',
        'storm-swarm-procedure',
    ],
    install_requires=[
        'perfectstorm-lib',
    ],
)
