# Messaging App

This simple web application lets you submit messages that are stored in a database and showed on the front page.

This application supports MySQL primary/replica setup: changes are written to the primary database, queries are read
from one of the replicas. Useful status information are shown on the front page.

It is a good candidate for testing service discovery (through DNS), load balancing and scaling.


## Setup

This application can be deployed in many ways, from a simple single-node setup to more complex distributed setups.
The application specification files shipped in this directory let you choose the setup you like most. More than that,
you can actually migrate from one setup to a more complex one with zero downtime!

The following walk-through explain how you can make your application evolve from the most simple setup to the more
complex ones.


### 0: Single node setup

This simple setup will run the frontend web app alongside MySQL on the same node. It does not require any special
deployers, only the Docker one.

1. Import the application specification:

       $ stormctl update -f examples/messaging/00-app-single-node.yml
       Group created: docker-hosts
       Group created: frontend
       Group created: mysql-primary
       App created: messaging
       Recipe created: frontend
       Recipe created: mysql-primary

1. Choose a Docker host where to run your containers. You can find the names of the available Docker hosts with:

       $ stormctl groups members docker-hosts -q

1. Ensure the Docker executor is running:

       $ deployers/ps-docker

1. Start the frontend web app and MySQL on that node:

       $ stormctl triggers run recipe -x recipe=frontend -x targetNode=<node name>
       $ stormctl triggers run recipe -x recipe=mysql-primary -x targetNode=<node name>

Now you can visit the web application by typing the address of the node in your browser. Enjoy!


### 1: Multi-node setup

This setup runs multiple frontend nodes that will connect to a single MySQL instance. The frontend nodes will be
load-balanced and they will discover MySQL using Consul.

1. Import the application specification:

       $ stormctl update -f examples/messaging/01-app-multi-node.yml
       Group updated: docker-hosts
       Group updated: frontend
       Group updated: mysql-primary
       App updated: messaging
       Recipe updated: frontend
       Recipe updated: mysql-primary

1. Ensure the Consul and load-balancer executors are running:

       $ deployers/ps-consul -n docker-hosts
       $ deployers/ps-loadbalancer -n docker-hosts

1. Start a couple of frontend nodes:

       $ stormctl triggers run recipe -x recipe=frontend
       $ stormctl triggers run recipe -x recipe=frontend
       ...

The load balancer will automatically register every frontend node you bring up. Visit the load balancer address to
see the home page (you can find the address from the output of `ps-loadbalancer`). If you refresh the page, you
should see the **Name** field constantly changing: that't the load balancer choosing a different frontend node
at every request.

Every frontend node you bring up will also be able to autonomously connect to MySQL. Check the **Primary** field:
it should point to the address of your MySQL server (except for the first frontend node that we brought up in the
previous setup: that will use the local `172.17.0.1:3306` address).

The application should work just fine without any tuning or configuration. Note how you can add/remove frontend nodes
at any time without downtime. Also note that you can start frontend containers manually: you are not forced to use
recipes. However you start the frontend containers, they will still be recognized and added to the load balancer.
You can also try to remove and re-deploy the MySQL server, and the application will still work, although this
operation will cause downtime and will also cause data loss (unless you make backups).

You're done, congratulations!


## 2: Multi-node setup with MySQL replicas

This setup runs multiple frontend nodes and multiple MySQL replica nodes. Like before, frontend is load-balanced,
MySQL is discovered through Consul. The MySQL server we brought up in the first setup will act as the primary node.

1. Import the application specification:

       $ stormctl update -f examples/messaging/02-app-multi-node-with-db-replica.yml
       Group updated: docker-hosts
       Group updated: frontend
       Group updated: mysql-primary
       Group updated: mysql-replica
       App updated: messaging
       Recipe updated: frontend
       Recipe updated: mysql-primary
       Recipe updated: mysql-replica
       Recipe updated: mysql-make-primary
       Recipe updated: mysql-make-replica
       Group created: old-frontend
       Recipe created: stop-old-frontend

1. Start one or more MySQL replica servers:

       $ stormctl triggers run recipe -x recipe=mysql-replica -x params='{"SERVER_ID":"2"}'
       $ stormctl triggers run recipe -x recipe=mysql-replica -x params='{"SERVER_ID":"3"}'
       $ stormctl triggers run recipe -x recipe=mysql-replica -x params='{"SERVER_ID":"..."}'

   Be sure to use a different `SERVER_ID` for each replica, otherwise MySQL will complain.

   Don't use `{"SERVER_ID":"2"}`: that has already been used for the first MySQL node.

1. After you have started enough servers, you can start replication on them with this recipe:

       $ stormctl triggers run recipe -x recipe=mysql-make-replica

   This recipe will automatically run on all nodes that are part of the `mysql-replica` group.

   Run this recipe whenever you start new replica servers or whenever the primary node changes (more on this later).

1. The old frontend nodes were not configured to use replica databases. They will still work, but they will only talk
   to the MySQL primary node. For this reason, you have to remove all or some frontend nodes and start new ones, with
   the updated recipe. To avoid downtime, it's recommended (but not required) to start new nodes before removing the
   old ones.

   Starting the new nodes is done exactly as before:

       $ stormctl triggers run recipe -x recipe=frontend
       $ stormctl triggers run recipe -x recipe=frontend
       ...

   Removing the old nodes is easy too: the application specification comes with an `old-frontend` group that
   automatically matches all frontend nodes that are not using the replica, and with a `stop-old-frontend` recipe
   that you can run to get rid of all the old containers in one shot:

       $ stormctl triggers run recipe -x recipe=stop-old-frontend

If you visit the web page now, you should see that the field **Replica** appeared. The web application will write
changes to the primary node and read entries from any of the replica nodes.

You can play by spawining or removing frontend and replica nodes, and see how the whole application remains operative.


### MySQL primary node replacement

The application will only break if the MySQL primary goes down. If that happens, manual steps are required to recover:

1. Choose a MySQL replica node to be the new primary. You can find the information about the running replica nodes
   with:

       $ stormctl groups members mysql-replica -q

1. Once you have decided, remove the container from the `mysql-replica` group:

       $ stormctl groups members mysql-replica --remove <replica name>

1. Turn the replica node into a primary node with the `mysql-make-primary` recipe:

       $ stormctl triggers run recipe -x recipe=mysql-make-primary -x targetNode=<replica name>

   The recipe will take care of automatically adding the container to the `mysql-primary` group.

1. Update all replica nodes to use the new primary:

       $ stormctl triggers run recipe -x recipe=mysql-make-replica

Now if you try to access the web application again, you should see that it's still perfectly functional.


### 3: Multi-region setup

In the multi-region setup the application is running over three regions demoninated: `us-west-1`, `eu-central-1` and
`ap-southeast-1`. Each region is running a load balancer, frontend nodes, MySQL replica nodes. The MySQL primary
node is assumed to be in `us-west-1`.

This setup can be brough up and visualized using `examples/messaging/03-app-multi-region.yml`. The specifications in
`examples/messaging/03-app-multi-region-extra.yml` provide additional visualization models.

The setup (from scratch) looks like this:

1. Import the application specification:

       $ stormctl update -f examples/messaging/03-app-multi-region.yml
       Group created: docker-hosts
       Group created: us-west-1
       Group created: eu-central-1
       Group created: ap-southeast-1
       Group created: frontend
       Group created: mysql-primary
       Group created: mysql-replica
       App created: messaging
       Recipe created: frontend
       Recipe created: mysql-primary
       Recipe created: mysql-replica
       Recipe created: mysql-make-primary
       Recipe created: mysql-make-replica

   You may need to adjust the queries for `us-west-1`, `eu-central-1` and `ap-southeast-1` to fit your needs.
   Use `stormctl edit <region name>` to do it.

1. Start the Docker deployer:

       $ deployers/ps-docker

1. Start a Consul per region with federation:

       $ deployers/ps-consul -n us-west-1
       $ deployers/ps-consul -n eu-central-1 -f us-west-1
       $ deployers/ps-consul -n ap-southeast-1 -f us-west-1 -f eu-central-1

1. Start a load balancer per region:

       $ deployers/ps-loadbalancer -n us-west-1
       $ deployers/ps-loadbalancer -n eu-central-1
       $ deployers/ps-loadbalancer -n ap-southeast-1

1. Start as many frontend nodes as you want:

       $ stormctl triggers run recipe -x recipe=frontend
       $ stormctl triggers run recipe -x recipe=frontend
       ...

   The frontend nodes will be started across all the regions. Use `-x targetAnyOf=<region name>` if you want to
   start a node in a particular region.

1. Start exactly one MySQL primary node:

       $ stormctl triggers run recipe -x recipe=mysql-primary

   The primary node will be started on `us-west-1`.

1. Start as many MySQL replica servers as you want:

       $ stormctl triggers run recipe -x recipe=mysql-replica -x params='{"SERVER_ID":"2"}'
       $ stormctl triggers run recipe -x recipe=mysql-replica -x params='{"SERVER_ID":"3"}'
       $ stormctl triggers run recipe -x recipe=mysql-replica -x params='{"SERVER_ID":"..."}'

   Like before, be sure to use different values for `SERVER_ID` each time.

   The replica nodes will be started across all the regions. Use `-x targetAnyOf=<region name>` if you want to
   start a node in a particular region.

1. Start replication:

       $ stormctl triggers run recipe -x recipe=mysql-make-replica
