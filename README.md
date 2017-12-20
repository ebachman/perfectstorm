# Perfect Storm

Prototype for application specification, visualization and discovery.


## Quick Start

Follow these steps to bring up the Perfect Storm API Server (a.k.a _Teacup_) and interact with it.

The API server uses [Topology](https://github.com/MosaixSoft/MosaixTopology) and [Neo4j](https://neo4j.com/) as its
primary data source. Be sure to have them up and running before starting.

1. First of all, create a Python virtual environment:

       $ python3 -m venv env
       $ . env/bin/activate

1. Be sure to have the latest version of `pip`, a tool for installing Python packages:

       $ pip install --upgrade pip

1. Install the requirements for this project:

       $ pip install -r requirements.txt

   This will also install all the subprojects in "development mode".

1. Initialize the local database:

       $ ./core/manage.py migrate
       Operations to perform:
         Apply all migrations: admin, auth, contenttypes, sessions
       Running migrations:
       ...

1. (Optional) If Noe4j is running on another host, or without the default username and password combination,
   you will need to specify some additional environment variables: `DJANGO_NEO4J_URL`, `DJANGO_NEO4J_USERNAME`
   and `DJANGO_NEO4J_PASSWORD`.

   You can add them at the bottom of your `env/bin/activate` so that they are loaded automatically every time
   you start using the Python virtual environment:

       $ echo 'DJANGO_NEO4J_URL=bolt://10.20.30.40/' >> env/bin/activate
       $ echo 'DJANGO_NEO4J_USERNAME=user' >> env/bin/activate
       $ echo 'DJANGO_NEO4J_PASSWORD=secret' >> env/bin/activate

Now you're ready to start the API Server!

    $ stormd
    Listening on http://127.0.0.1:8000/
    [I 171218 04:15:56 process:133] Starting 8 processes

You can now interact with the API at http://127.0.0.1:8000/v1/ and read the documentation
at http://127.0.0.1:8000/docs/.

Whenever you close the terminal and come back in, remember to re-activate the Python virtual enviornment before
starting the API Server:

    $ . env/bin/activate


## Using the client

Once the server is running, create your first application together with its components:

    $ stormctl create -f examples/tea-service.yml
    Group created: teacup
    Group created: teapot
    Group created: tea-maker
    Application created: tea-service

List the groups that have been created:

	$ stormctl groups ls
	groups:
	- name: tea-maker
	  query: xyz
	  services:
	  - name: request
		port: 50
		protocol: tcp
	- name: teacup
	  query: xyz
	  services:
	  - name: tea-egress
		port: 20
		protocol: tcp
	  - name: tea-ingress
		port: 10
		protocol: tcp
	- name: teapot
	  query: xyz
	  services:
	  - name: tea-leaves-ingress
		port: 40
		protocol: tcp
	  - name: water-ingress
		port: 30
		protocol: tcp

List apps:

	$ stormctl apps ls
	apps:
	- components:
	  - teapot => teacup[tea-ingress]
	  - tea-maker => teapot[water-ingress]
	  - tea-maker => teapot[tea-leaves-ingress]
	  expose: []
	  name: tea-service

Edit a group:

	$ stormctl groups edit teacup

Edit the application:

	$ stormctl apps edit tea-service

Delete the application and its groups:

	$ stormctl delete -f examples/tea-service.yml
	Group deleted: teacup
	Group deleted: teapot
	Group deleted: tea-maker
	Application deleted: tea-service


## Executors

The repository ships with various _executors_: processes that interact with the API Server and that can create and
manage resources on the cloud. Executors act in respose to _triggers_ from the user. Triggers can be sent from the
client using the `stormctl triggers run ...` command.


## Demo and examples

This repository ships with a few demos and examples that you can try out with minimal effort:

1. [WordPress with MySQL](examples/blog/README.md)
1. [Distributed web application with MySQL replication](examples/messaging/README.md)
1. [Example "tea service" application](examples/tea/README.md)


## Docker

To build a Docker image:

    $ docker build -t perfect-storm:0.1 .

Running it is as simple as:

    $ docker run -d -p 8000:8000 perfect-storm:0.1

Database and documentation will be automatically built. The server will be listening on port 8000.
