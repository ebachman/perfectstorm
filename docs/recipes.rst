Recipes
#######

Recipes are stored procedures that can be executed on any execution engine (such as containers or virtual machines).
Recipes contain scripts that can be used to, for example:

* deploy or remove containers;
* execute code inside containers;
* change the properties of a virtual machine.

Recipes are stored by the API server and can be run at any time. When a recipe is run, users can override certain
values to change the behavior of the recipes.

The content of recipes can be run by arbitrary executors, there is no fixed syntax, and you are free to write your own.
The following example is using the `docker executor`_, which takes a list of commands that can be passed to the
`docker` command line client::

    recipe:
      name: example
      type: docker
      content: |
        run:
          - '-p 3306:3306 -v /var/lib/mysql:/var/lib/mysql mysql:latest'
          - '-p 80:80 -n web-server nginx:latest'

By changing the **type** of the recipe you can use different executors


Features
========

Parameters
----------

Recipes are parametric, in the sense that you can change their content with user supplied input. For example::

    recipe:
      name: example
      type: docker
      content: |
        run:
          - '-p 80:80 ngnix:$VERSION'
      params:
        VERSION: latest

The parameter ``VERSION`` can be supplied when running the recipe to change the tag for ``nginx`` from the default
value of ``latest``. Default values can be specified when defining a recipe, but don't need to.


Reference
=========

Recipe specifications have the following fields:

* **name** (String): unique name identifying the recipe.

* **type** (String): this specifies the kind of content for the recipe. Different recipe executors will support
  different types of recipes.

* **content** (String): the script to be run. The exact semantics of **content** varies depending on the **type**.

* **options** (Optional, Map, Default: empty): a set of key-value pairs that change the behavior of recipes. The
  semantics for **options** are the same for all types of recipes, although certain executors might not support all the
  possible options. Options are:

  * **consulDns** (Optional, Boolean, Default: true): If `true`, any resource that is created by this recipe will use
    the local Consul DNS. This requires the Consul executor to be running, otherwise name resolution won't work. If
    `false`, resources will use the default DNS.

* **params** (Optional, Map, Default: empty): a set of arbitrary key-value pairs that will be replaced inside the
  recipe content by the executor at runtime.

* Target specification: at least one of the following fields must be specified, either when defining a recipe or when
  running it.

  * **targetNode** (Optional, String, Default: null): ID or name of the node where the recipe will run.

  * **targetAnyOf** (Optional, String, Default: null): name of a group. The executor will execute the recipe on a one
    of the members of that group. The choice is not purely random: the executor will take care of finding a suitable
    member.

  * **targetAllIn** (Optional, String, Default: null): name of a group. The recipe will be executed on all the suitable
    nodes of this group.

  You can specify these fields at the same time, but only one will be considered. The order in which these fields are
  considered is: **targetNode**, **targetAnyOf**, **targetAllIn**.


Submitting a recipe
===================

Submitting a recipe can be done via ``stormctl``::

    $ stormctl update -f <recipe file>

Or via the API::

    curl -X PUT -d '<recipe>' http://127.0.0.1:28482/v1/recipes/


Running a recipe
================

A recipe can be run by issuing a :doc:`trigger <triggers>` of type `recipe`. Via ``stormctl``::

    $ stormctl triggers run recipe -x recipeName=<recipe name>

Via the API::

    $ curl -X PUT -d '{"recipeName":"<recipe name>"}' http://127.0.0.1:28482/v1/triggers/

When running a recipe you can override any of these fields:

* **options**
* **params**
* **targetNode**
* **targetAnyOf**
* **targetAllIn**

When running a recipe, either a target must be specified inside the recipe specification, or it must be supplied
when starting the trigger.
