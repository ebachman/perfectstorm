from setuptools import setup

setup(
    name='perfectstorm-cli',
    version='0.1',
    scripts=['stormctl'],
    install_requires=[
        'PyYAML >= 3, < 4',
        'jsonmodels >= 2.2, < 3',
        'simple-rest-client >= 0.3, <= 0.4',
    ],
)
