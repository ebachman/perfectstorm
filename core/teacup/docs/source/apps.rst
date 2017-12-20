Applications
============

An application is a set of components, together with the interdependencies between those components. Components are
`groups </groups>` of resources. Applications are used to visualize and define how groups are supposed to interact
with each other and what services are exposed to the user. An example is a simple two-tier application composed of a
web server and a database server.


Creating an application
-----------------------

A group can be defined by writing a specification like this::

    groups:
      - name: web-server
        members: [nginx-container]
        services:
          - name: http
            protocol: tcp
            port: 80

      - name: database
        members: [postgres-container]
        services:
          - name: postgres
            protocol: tcp
            port: 5432

    applications:
      - name: two-tier-app
        components:
          - web-server => postgres-container[postgres]
        expose:
          - web-server[http]

Then, from the command line client::

    stormctl create -f app.yaml
