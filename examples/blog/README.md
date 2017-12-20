# WordPress and MySQL

This is a simple demo application using a distributed WordPress deployment and a single-node MySQL server.

1. Define the blog application:

       $ stormctl update -f examples/blog/wordpress.yml

1. Ensure the required executors are running:

       $ deployers/ps-docker
       $ deployers/ps-consul -n blog-nodes
       $ deployers/ps-loadbalancer -n blog-nodes

1. Start MySQL Server:

       $ stormctl triggers run recipe -x recipe=mysql

   Once MySQL has started, it will be published automatically as a service on Consul. Applications will be able to
   reach it at `mysql-mysql.service.consul` using the Consul DNS server.

1. Start WordPress:

       $ stormctl triggers run recipe -x recipe=wordpress

   After this, WordPress will connect to MySQL and will be perfectly functional and reachable on port 80.

   Feel free to run this command multiple times to spawn multiple copies of WordPress sharing the same database. If you
   are using the load balancer, all new nodes will be added.

The interesting part here is that we did not have to give WordPress any specific configuration in order for it to
find MySQL Server: the `wordpress` recipe works in every environment without any modification. We also did not have to
modify the images for MySQL or WordPress: we are using the stock ones from the Docker Hub. The service discovery
mechanism is acting transparently through Consul.
