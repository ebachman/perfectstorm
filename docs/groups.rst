Groups
======

Groups are logical sets of resources (containers, servers, networks, ...) that share common properties. An example of
group is: `the set of all containers running Python 3.6 or later`.

Resources can be added to a group in three ways:

* by starting resources inside the group;
* by manually adding pre-existing resources to the group;
* by defining a query to match containers, e.g. `all containers running Python` or `all containers using the
  bridge network` or `all containers started after the 3rd of January`.

In a way, groups can be seen as a type of logical visualization of resources in the cloud. It is important to note that
a resource can be part of multipe groups, depending on the query used to construct the group.


Group Management
----------------
Groups can be managed using the stormctl command line client. A group is defined
using a specification in a YAML file and is identified by a name. The examples
directory contains sample YAML files with the group specification.
The following group operations are possible:
    - * create -f <YAML_FILE>
    - * ls
    - * get <GROUP_NAME>
    - * update -f <YAML_FILE>
    - * edit -f <YAML_FILE>
    - * delete <GROUP_NAME>


Sample group
-------------

A group can be defined as follows::

 group:
    name: wordpress
    query:
      type: CONTAINER
      image:
        name:
          $startsWith: 'wordpress:'

 group:
    name: blog-nodes
    query:
      type: PHYSICAL_SERVER
