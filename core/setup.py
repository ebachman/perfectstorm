from setuptools import setup, find_packages

setup(
    name='perfectstorm-core',
    version='0.1',
    packages=find_packages(),
    package_data={
        'teacup.docs': [
            'source/*.rst',
            'source/conf.py',
        ],
    },
    scripts=['stormd'],
    install_requires=[
        'Django >= 1.11, < 1.12',
        'PyYAML >= 3.12, < 4',
        'Sphinx >= 1.6.5, < 1.7',
        'djangorestframework >= 3.7, < 3.8',
        'gevent >= 1.2, < 1.3',
        'jsonfield >= 2, < 3',
        'py2neo >= 3, < 4',
        'requests >= 2.13, < 3',
        'requests_toolbelt >= 0.7, < 1',
        'tornado >= 4.5, < 4.6',
    ],
    zip_safe=False,
)
