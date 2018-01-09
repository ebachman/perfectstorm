from setuptools import setup

setup(
    name='perfectstorm-cli',
    version='0.1',
    scripts=['stormctl'],
    install_requires=[
        'perfectstorm-lib',
        'pyyaml >= 3, < 4',
    ],
)
