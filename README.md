# Perfect Storm

Perfect Storm gives you a high-level view of your resources in the cloud.
It separates logical components of your application (web service,
database, load balancer, key-value store, ...) from the low level
resources running in your cloud (containers, virtual machines,
networks, ...).

The way Perfect Storm works is by letting you define _groups_ of low-level
resources and specify how they interact with each other. For example, a
simple web application with a PostgreSQL database running on Docker Swarm
may be defined through the following YAML specification:

    # Define a group named 'frontend' that contains all the Swarm
    # tasks (i.e. containers) using the 'coolstuff/webapp' image,
    # any version.
    # All the Swarm tasks in this group will are serving HTTP
    # requests on port 80.
    - group:
        name: frontend
        query:
          type: swarm-task
          image:
            $regex: '^coolstuff/webapp:'
        services:
          - name: http
            protocol: tcp
            port: 80

    # This 'database' group contains all PostgreSQL tasks (containers).
    # These tasks are listening on port 5432.
    - group:
        name: database
        query:
          type: swarm-task
          image:
            $regex: '^library/postgres:'
        services:
          - name: postgres
            protocol: tcp
            port: 5432

    # Define a 'webapp' application composed of the 'frontend' group
    # and the 'database' group. Frontend talks to database using the
    # 'postgres' protocol on port 5432. Users can talk to frontend
    # using the 'http' protocol on port 80.
    - application:
        name: messaging
        components:
          - frontend => database[postgres]
        expose:
          - frontend[http]

Groups and applications reflect the status of the resources in the cloud
in real-time. Groups can be defined at any time, in a very flexible way,
using any kind of query you like.

Some use cases include:

* have a logical overview of your resources in the cloud and their status;
* monitor and orchestrate upgrades;
* look for anomalies in your cloud resources;


## Overview

Perfect Storm has a modular architecture. It's composed by a _Core API
Server_, which stores information about groups and resources, and various
_executors_, which talk to the Core API Server and provide functionality
to discover resources in the cloud and modify them.
[MongoDB](https://www.mongodb.com/) is used as the storage backend.

Perfect Storm is meant to be compatible with as many clouds as possible,
but at the moment it supports only
[Docker Swarm](https://docs.docker.com/engine/swarm/).

**Perfect Storm is currently under active development.** Stay tuned!


## Quick Start

### Core API Server

1. Start an instance of MongoDB. If you're using Docker:

       docker run -d -p 27017:27017 mongo

1. Create a [Python virtual environment](https://docs.python.org/3/library/venv.html):

       python3 -m venv env
       . env/bin/activate

1. Make sure to have the latest version of `pip` and `wheel` installed:

       pip install --upgrade pip wheel

1. Install the requirements for this project:

       pip install -r requirements.txt

   This will also install all the subprojects in "development mode".

1. (Optional) If MongoDB is not running on the local host, or if you want
   to customize the connection, you need to set the `STORM_MONGODB`
   environment variable. This is an URI in the format:

       mongodb://<user>@<host>:<port>/<database>

   Example:

       mongodb://10.0.1.7/perfectstorm

   You can add this environment variable at the end of your
   `env/bin/activate` file, so that it will be loaded automatically every
   time you start using the Python virtual environment:

       echo 'STORM_MONGODB=mongodb://10.0.1.7/perfectstorm' >> env/bin/activate

Now you're ready to start the API Server!

    stormd

You can now interact with the API at http://127.0.0.1:28482/v1/, either
using your browser or from the command line.

Whenever you close the terminal and come back in, remember to re-activate
the Python virtual enviornment before starting the API Server:

    . env/bin/activate


### Docker Swarm Executor

After you have set up and started the API Server, you can start the Docker
Swarm Executor. This will discover all the Swarm services and tasks
running in your Swarm cluster, as well as providing ways to update your
resources.

If you need help setting up a Swarm cluster, check out the
[tutorial](https://docs.docker.com/get-started/part4/#understanding-swarm-clusters).

Once you have a cluster up and running, you can start the executor with:

    storm-swarm --host=<host>:<port>

Replace `<host>` and `<port>` with the address of one of the Docker Swarm
Managers. (Note: TLS authentication is currently not supported. You must
have your Swarm manager running without TLS. Support for TLS will be added
in the near future.)

Once the Swarm Executor starts, it will publish all your services and
tasks to the API Server.


### Command line client

Once the API Server is running and the Swarm Executor has started, you
can browse your cloud resources with `stormctl`:

    $ stormctl resources ls
    ID                           TYPE            NAMES                                                STATUS     HEALTH
    res-6s38trDn0QOgVWIj3XMZkS   swarm-service   leomsds9honhd6b2saraxa3d8, hello-world               running    unknown
    res-6sD7G9dscs1qNJOHjRhMJY   swarm-task      05vjdocfpu9ipi8lqznkzobcr, ba0f46fc0f6fd7fc13fa...   stopped    unknown
    res-6s38tsspSiYAovqeefID3U   swarm-task      03rjz2m86os6cusfn22ut251a, 9e938ba2bc0643b1393c...   stopped    unknown
    res-6s38tuXrv0hf8LOaFnDqMW   swarm-task      0kc5twgnj79rntn8cvnh1yuuo, hello-world.1, hello...   starting   unknown
    res-6s38twCuNIr9RkwVqv9TfY   swarm-task      0gt90wwwaku7ih8c4yjilsep8, 9e848cd8299cb88683a2...   stopped    unknown
    res-6s38tzWzHtA84a2N3B0kHc   swarm-task      0co3v2r04o3u4c4hwh6xeyzth, 1b8c629a8b72053a236c...   stopped    unknown
    res-6rZgYCpC5LdUYQovLeu3dk   swarm-cluster   j7qt6ftt5nzsdfw0dtp7oquf7                            running    unknown

Create your first application together with its components:

    $ stormctl import -f examples/hello-world.yml

List the groups that have been imported:

	$ stormctl group ls
	ID                             NAME
    group-58JYE3yBOmGXZhgY0Ufj12   hello-world

Inspect a group:

    $ stormctl group get hello-world
    id: group-58JYE3yBOmGXZhgY0Ufj12
    name: hello-world
    query:
      image:
        $regex: '^library/hello-world:'
      type: swarm-task
    services: []
    include: []
    exclude: []

List the applications:

	$ stormctl apps ls
	ID                           NAME
    app-58KQmtS0v0oMUhe3F1iQs0   hello-world

Inspect an application:

    $ stormctl application get hello-world
    id: app-58KQmtS0v0oMUhe3F1iQs0
    name: hello-world
    components:
    - group-58JYE3yBOmGXZhgY0Ufj12
    links: []
    expose: []


## Demo and examples

This repository ships with a few demos and examples that you can try out with minimal effort:

1. [WordPress with MySQL](examples/blog/README.md)
1. [Distributed web application with MySQL replication](examples/messaging/README.md)
1. [Example "tea service" application](examples/tea/README.md)


## Tests

Automated tests are based on the [pytest framework](https://pytest.org/).
To run them use:

    pytest

See `pytest -h` or the [pytest documentation](https://pytest.org/) for
usage information and examples.
