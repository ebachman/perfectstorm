# Perfect Storm

Prototype for application specification, visualization and discovery.


## Quick Start

Follow these steps to bring up the Perfect Storm API Server (a.k.a _Teacup_) and interact with it.

The API server uses [MongoDB](https://www.mongodb.com/) as its storage backend. Be sure to have it
up and running before starting.

1. First of all, create a Python virtual environment:

       $ python3 -m venv env
       $ . env/bin/activate

1. Make sure to have the latest version of `pip` and `wheel`:

       $ pip install --upgrade pip wheel

1. Install the requirements for this project:

       $ pip install -r requirements.txt

   This will also install all the subprojects in "development mode".

1. (Optional) If MongoDB is running on another host, or if you want to customize the connection, you can
   specify some additional environment variables:

   - `DJANGO_MONGO_HOST`: host to connect to, defaults to `127.0.0.1`;
   - `DJANGO_MONGO_PORT`: port to connecto to, defaults to `27017`
   - `DJANGO_MONGO_DB`: name of the database, defaults to `perfectstorm`.

   You can add these environment variables at the bottom of your `env/bin/activate` so that they are loaded
   automatically every time you start using the Python virtual environment:

       $ echo 'DJANGO_MONGO_HOST=127.0.0.1' >> env/bin/activate
       $ echo 'DJANGO_MONGO_PORT=27017' >> env/bin/activate
       $ echo 'DJANGO_MONGO_DB=perfectstorm' >> env/bin/activate

Now you're ready to start the API Server!

    $ stormd --bootstrap
    Bootstrap completed
    Listening on http://127.0.0.1:8000/
    [2018-01-02 18:16:43] Starting 8 processes

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
