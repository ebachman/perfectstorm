$(function() {
  $.getJSON("/v1/apps/", function(apps) {
    console.log("here");
    for (var i = 0; i < apps.length; i++) {
      var app = apps[i];
      var appName = app.name;
      console.log(appName);
      $("#app-list").append('<li><a href="?app=' + appName + '">' + appName + '</li>');
    }
  });

  var getParam = function(name) {
    var match = RegExp('[?&]' + name + '=([^&]*)').exec(window.location.search);
    return match && decodeURIComponent(match[1].replace(/\+/g, ' '));
  }

  var getGroupMembers = function(groupName) {
    return $.getJSON("/v1/groups/" + groupName + "/members/?q={\"status\":\"UP\"}", function(members) {
      groupMembers[groupName] = members;
    });
  }

  var groupMembers = {};
  var appName = getParam("app");

  if (!appName)
    return;

  $.getJSON("/v1/apps/" + appName + "/", function(app) {
    var promise = $.when();

    for (var j = 0; j < app.components.length; j++) {
      var groupName = app.components[j];
      promise = promise.then(getGroupMembers.bind(null, groupName));
    }

    promise.then(function() {
      window.graph = prepareData(app, groupMembers);
      createGraph("svg", graph);
    });
  });
})

function createGraph(eleId, data) {
  var colors = d3.scaleOrdinal(d3.schemeCategory10);

  var svg = d3.select(eleId),
      width = $(eleId).width(),
      height = $(eleId).height(),
      node,
      link;

  svg.append('defs').append('marker')
      .attrs({'id':'arrowhead',
          'viewBox':'0 -5 10 10',
          'refX':9,
          'refY':0,
          'orient':'auto',
          'markerWidth':10,
          'markerHeight':10,
          'xoverflow':'visible'})
      .append('svg:path')
      .attr('d', 'M 0,-5 L 10 ,0 L 0,5')
      .attr('fill', '#000')
      .style('stroke','none');

  var simulation = d3.forceSimulation()
      .force("link", d3.forceLink().id(function (d) {return d.id;}).distance(300).strength(1))
      .force("charge", d3.forceManyBody())
      .force("center", d3.forceCenter(width / 2, height / 2));


  update(data.links, data.nodes);

  function update(links, nodes) {
      link = svg.selectAll(".link")
          .data(links)
          .enter()
          .append("line")
          .attr("class", "link")
          .attr('marker-end','url(#arrowhead)')

      link.append("title")
          .text(function (d) {return d.type;});

      edgepaths = svg.selectAll(".edgepath")
          .data(links)
          .enter()
          .append('path')
          .attrs({
              'class': 'edgepath',
              'id': function (d, i) {console.log(i);return 'edgepath' + i;}
          })
          .style("pointer-events", "none");

      edgelabels = svg.selectAll(".edgelabel")
          .data(links)
          .enter()
          .append('text')
          .style("pointer-events", "none")
          .attrs({
              'class': 'edgelabel',
              'id': function (d, i) {return 'edgelabel' + i},
              'font-family':'sans-serif',
              'font-size': 14,
              'fill': '#112AC8'
          });

      edgelabels.append('textPath')
          .attr('xlink:href', function (d, i) {return '#edgepath' + i})
          .style("text-anchor", "middle")
          .style("pointer-events", "none")
          .attr("startOffset", "50%")
          .text(function (d) {return d.type});

      node = svg.selectAll(".node")
          .data(nodes)
          .enter()
          .append("g")
          .attr("class", "node")
          .call(d3.drag()
                  .on("start", dragstarted)
                  .on("drag", dragged)
          );

      //node.append("circle")
      //    .attr("r", 5)
      //    .style("fill", function (d, i) {return colors(i);})
      node.append("ellipse")
          .attr("rx", 75)
          .attr("ry", 50)
          .style("fill", function (d, i) {return colors(i);});


      node.append("title")
          .text(function (d) {return d.name;});

      node.append("text")
          .attr("text-anchor", "middle")
          .attr("font-family", "sans-serif")
          .text(function (d) {return d.name;});

      node.append("text")
          .attr("text-anchor", "middle")
          .attr("font-family", "sans-serif")
          .attr("font-size", "70%")
          .attr("style", "transform:translate(0, 20px)")
          .text(function (d) {return d.comment;});

      simulation
          .nodes(nodes)
          .on("tick", ticked);

      simulation.force("link")
          .links(links);
  }

  function ticked() {
      link
          .attr("x1", function (d) {return d.source.x;})
          .attr("y1", function (d) {return d.source.y;})
          .attr("x2", function (d) {
            var a = 75,
                b = 50;
            var dx = d.source.x - d.target.x,
                dy = d.source.y - d.target.y;

            return d.target.x + a * b * dx / Math.sqrt(a * a * dy * dy + b * b * dx * dx);
          })
          .attr("y2", function (d) {
            var a = 75,
                b = 50;
            var dx = d.source.x - d.target.x,
                dy = d.source.y - d.target.y;

            return d.target.y + a * b * dy / Math.sqrt(a * a * dy * dy + b * b * dx * dx);
          });

      node
          .attr("transform", function (d) {return "translate(" + d.x + ", " + d.y + ")";});

      edgepaths.attr('d', function (d) {
          return 'M ' + d.source.x + ' ' + d.source.y + ' L ' + d.target.x + ' ' + d.target.y;
      });

      edgelabels.attr('transform', function (d) {
          if (d.target.x < d.source.x) {
              var bbox = this.getBBox();

              rx = bbox.x + bbox.width / 2;
              ry = bbox.y + bbox.height / 2;
              return 'rotate(180 ' + rx + ' ' + ry + ')';
          }
          else {
              return 'rotate(0)';
          }
      });
  }

  function dragstarted(d) {
      if (!d3.event.active) simulation.alphaTarget(0.3).restart()
      d.fx = d.x;
      d.fy = d.y;
  }

  function dragged(d) {
      d.fx = d3.event.x;
      d.fy = d3.event.y;
  }

  return svg
}

/**
* Prepare data for the d3 graph
* @param  {Object} data Source data from Links.json
* @return {Object}      Parsed data for rendering
*/
function prepareData(graph, groupMembers) {
    let nodes = []
    let links = []

    if( graph.components ){
        _.each( graph.components, function(nodeName){
            let node = {
                "name": nodeName,
                "comment": "members: " + groupMembers[nodeName].length,
                "id": nodeName
            }
            nodes.push(node)
        })
    }
    if( graph.expose ){
        let node = {
            "name": "user",
            "id": "user"
        }
        nodes.push(node)
        _.each( graph.expose, function(exposeName){
            let link = {}
            if( exposeName.component && exposeName.service ){
                link["source"] = "user"
                link["target"] = exposeName.component
                link["type"] = exposeName.service
                links.push(link)
            }
        })
    }
    if( graph.links ){
        _.each( graph.links, function(data){
            let link = {}
            if( data["src_component"] && data["dest_component"] ){
                link["source"] = data["src_component"]
                link["target"] = data["dest_component"]
                if( data["dest_service"] ) link["type"] = data["dest_service"]
                    links.push(link)
            }
        })
    }

    return { "nodes": nodes, "links": links}
}
