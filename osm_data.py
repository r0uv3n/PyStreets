from collections import namedtuple
from logging import Logger  # for typing
from math import sqrt

import osmread

import logger
from street_network import StreetNetwork

Coordinate = namedtuple("Coordinate", ["longitude", "latitude"])


# This class reads an OSM file and builds a graph out of it
class GraphBuilder(object):
    """Parse the input file and save its contents in memory

    Arguments:
        osm_path: Path of the .osm file to be used, located in the osm_dir given in settings.py. Not
        necessary if existing_data is True
        log_callback: Parent Logger; If None, logs to a new file.
        """

    latitude = 0
    longitude = 1

    def __init__(self, osm_path, name: str = None, log_callback: Logger = None):
        self.name = name
        # initialize logging
        self.logger = logger.init_logger(module="OSM_data", name=self.name, log_callback=log_callback)
        self.logger.info("Logging for OSM_data initialized")

        # initialize street network
        self.street_network = StreetNetwork()

        # coord pairs as returned
        self.coords = dict()

        # max and min latitude and longitude
        self.bounds = dict()
        self.bounds["min_lat"] = 9999
        self.bounds["max_lat"] = -9999
        self.bounds["min_lon"] = 9999
        self.bounds["max_lon"] = -9999

        # active copy of OSM data indexed by osm_id
        self.all_osm_relations = dict()
        self.all_osm_ways = dict()
        self.all_osm_nodes = dict()

        # nodes with specific landuse tags
        self.residential_nodes = set()
        self.industrial_nodes = set()
        self.commercial_nodes = set()

        # subset that is also connected to the street network
        self.connected_residential_nodes = set()
        self.connected_industrial_nodes = set()
        self.connected_commercial_nodes = set()

        # mapping from highway types to max speeds
        # we do this so there"s always a speed limit for every edge, even if
        # none is in the OSM data
        self.max_speed_map = {
            "motorway"    : 140,
            "trunk"       : 120,
            "primary"     : 100,
            "secondary"   : 80,
            "tertiary"    : 70,
            "road"        : 50,
            "minor"       : 50,
            "unclassified": 50,
            "residential" : 30,
            "track"       : 30,
            "service"     : 20,
            "path"        : 10,
            "cycleway"    : 1,  # >0 to prevent infinite weights
            "bridleway"   : 1,  # >0 to prevent infinite weights
            "pedestrian"  : 1,  # >0 to prevent infinite weights
            "footway"     : 1,  # >0 to prevent infinite weights
        }
        self.lane_map = {
            "residential": 2,
            "tertiary"   : 2,
            "secondary"  : 2,
            "primary"    : 2,
            "service"    : 1,
            "track"      : 1,
            "path"       : 1,
        }
        self.logger.info("Parsing .osm data")
        self.parse(osm_path)

        self.logger.info("Building Street Network")
        self.build_street_network()

        self.logger.info("Finding node categories")
        self.find_node_categories()

    def build_street_network(self):
        self.logger.debug("Adding boundaries to street network")
        if 9999 not in self.bounds.values() and -9999 not in self.bounds.values():
            self.street_network.set_bounds(self.bounds["min_lat"], self.bounds["max_lat"],
                                           self.bounds["min_lon"], self.bounds["max_lon"])

        # construct the actual graph structure from the input data
        for way in self.all_osm_ways.values():
            if "highway" in way.tags:
                if not way.nodes:
                    continue
                if not self.street_network.has_node(way.nodes[0]):
                    coord = self.coords[way.nodes[0]]
                    self.street_network.add_node(way.nodes[0], coord[self.longitude], coord[self.latitude])
                for i in range(0, len(way.nodes) - 1):
                    if not self.street_network.has_node(way.nodes[i + 1]):
                        coord = self.coords[way.nodes[i + 1]]
                        self.street_network.add_node(way.nodes[i + 1], coord[self.longitude], coord[self.latitude])
                    oneway = False
                    if "oneway" in way.tags:
                        if "oneway" == "Yes":
                            oneway = True

                    # calculate street length

                    length = self.length_haversine(way.nodes[i], way.nodes[i + 1])

                    # determine max speed
                    max_speed = 50
                    if way.tags["highway"] in self.max_speed_map.keys():
                        max_speed = self.max_speed_map[way.tags["highway"]]
                    if "maxspeed" in way.tags:
                        max_speed_tag = way.tags["maxspeed"]
                        if max_speed_tag.isdigit():
                            max_speed = int(max_speed_tag)
                        elif max_speed_tag.endswith("mph"):
                            max_speed = int(max_speed_tag.replace("mph", "").strip(" "))
                        elif max_speed_tag == "none":
                            max_speed = 140

                    # determine number of lanes
                    number_of_lanes = 1
                    if "lanes" in way.tags:
                        number_of_lanes = int(way.tags['lanes'])
                    else:
                        if way.tags['highway'] in self.lane_map.keys():
                            number_of_lanes = self.lane_map[way.tags['highway']]
                    if not oneway:
                        if "lanes:forward" in way.tags and "lanes:backward" in way.tags:
                            number_of_lanes_forward = int(way.tags['lanes:forward'])

                            number_of_lanes_backward = int(way.tags['lanes:backward'])
                        else:
                            number_of_lanes_forward = float(number_of_lanes) / 2
                            number_of_lanes_backward = float(number_of_lanes) / 2
                    # add street to street network
                    if oneway:
                        street = (way.nodes[i], way.nodes[i + 1])
                        if not self.street_network.has_street(street):
                            self.street_network.add_street(street, length, max_speed, number_of_lanes)
                    else:
                        forward_street = (way.nodes[i], way.nodes[i + 1])
                        if not self.street_network.has_street(forward_street):
                            # noinspection PyUnboundLocalVariable
                            self.street_network.add_street(forward_street, length, max_speed, number_of_lanes_forward)
                        backward_street = (way.nodes[i + 1], way.nodes[i])
                        if not self.street_network.has_street(backward_street):
                            # noinspection PyUnboundLocalVariable
                            self.street_network.add_street(backward_street, length, max_speed, number_of_lanes_backward)

        return self.street_network

    def find_node_categories(self):
        """Collect relevant categories of nodes in their respective sets"""
        # TODO there has to be a better way to do this
        # TODO do this inside class StreetNetwork?
        for relation in self.all_osm_relations.values():
            if "landuse" in relation.tags:
                if relation.tags["landuse"] == "residential":
                    self.residential_nodes = self.residential_nodes | self.get_all_child_nodes(relation.id)
                if relation.tags["landuse"] == "industrial":
                    self.industrial_nodes = self.industrial_nodes | self.get_all_child_nodes(relation.id)
                if relation.tags["landuse"] == "commercial":
                    self.commercial_nodes = self.commercial_nodes | self.get_all_child_nodes(relation.id)
        for way in self.all_osm_ways.values():
            if "landuse" in way.tags:
                if way.tags["landuse"] == "residential":
                    self.residential_nodes = self.residential_nodes | self.get_all_child_nodes(way.id)
                if way.tags["landuse"] == "industrial":
                    self.industrial_nodes = self.industrial_nodes | self.get_all_child_nodes(way.id)
                if way.tags["landuse"] == "commercial":
                    self.commercial_nodes = self.commercial_nodes | self.get_all_child_nodes(way.id)
        for node in self.all_osm_nodes.values():
            if "landuse" in node.tags:
                if node.tags["landuse"] == "residential":
                    self.residential_nodes = self.residential_nodes | self.get_all_child_nodes(node.id)
                if node.tags["landuse"] == "industrial":
                    self.industrial_nodes = self.industrial_nodes | self.get_all_child_nodes(node.id)
                if node.tags["landuse"] == "commercial":
                    self.commercial_nodes = self.commercial_nodes | self.get_all_child_nodes(node.id)
        street_network_nodes = set(self.street_network.get_nodes())
        self.connected_residential_nodes = self.residential_nodes & street_network_nodes
        self.connected_industrial_nodes = self.industrial_nodes & street_network_nodes
        self.connected_commercial_nodes = self.commercial_nodes & street_network_nodes

        if not self.connected_residential_nodes:
            self.logger.warn("Residential Nodes are empty")

        if not self.connected_industrial_nodes:
            self.logger.warn("Industrial Nodes are empty")
        if not self.connected_commercial_nodes:
            self.logger.warn("Commercial Nodes are empty")

    def parse(self, osm_file):
        for entity in osmread.parse_file(osm_file):
            if isinstance(entity, osmread.Node):
                self.all_osm_nodes[entity.id] = entity
                coord = Coordinate(latitude=entity.lat, longitude=entity.lon)
                self.adjust_borders(coord)
                self.coords[entity.id] = coord
            elif isinstance(entity, osmread.Way):
                self.all_osm_ways[entity.id] = entity
            elif isinstance(entity, osmread.Relation):
                self.all_osm_relations[entity.id] = entity

    def adjust_borders(self, coord):
        lon, lat = coord
        self.bounds["min_lat"] = min(self.bounds["min_lat"], lat)
        self.bounds["min_lon"] = min(self.bounds["min_lon"], lon)
        self.bounds["max_lat"] = max(self.bounds["max_lat"], lat)
        self.bounds["max_lon"] = max(self.bounds["max_lon"], lon)

    def get_all_child_nodes(self, osm_id):
        """given any OSM osm_id, construct a set of the ids of all descendant nodes"""
        if osm_id in self.all_osm_nodes.keys():
            return {osm_id}
        if osm_id in self.all_osm_relations.keys():
            children = set()
            for child in self.all_osm_relations[osm_id].members:
                children = children | self.get_all_child_nodes(child.member_id)
            return children
        if osm_id in self.all_osm_ways.keys():
            children = set()
            for ref in self.all_osm_ways[osm_id].nodes:
                children.add(ref)
            return children
        return set()  # TODO deal properly with members not on map

    def length_euclidean(self, id1, id2):
        # calculate distance on a 2D plane assuming latitude and longitude
        # form a planar uniform coordinate system (obviously not 100% accurate)
        p1 = self.coords[id1]
        p2 = self.coords[id2]
        # assuming distance between to degrees of latitude to be approx.
        # 66.4km as is the case for Hamburg, and distance between two
        # degrees of longitude is always 111.32km
        dist = sqrt(((p2[self.latitude] - p1[self.latitude]) * 111.32) ** 2
                    + ((p2[self.longitude] - p1[self.longitude]) * 66.4) ** 2)
        return dist * 1000  # return distance in m

    def length_haversine(self, id1, id2):
        """Calculate distance using the haversine formula, which incorporates earth curvature. See
        http://en.wikipedia.org/wiki/Haversine_formula"""
        lat1 = self.coords[id1][self.latitude]
        lon1 = self.coords[id1][self.longitude]
        lat2 = self.coords[id2][self.latitude]
        lon2 = self.coords[id2][self.longitude]
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        delta_lon = lon2 - lon1
        delta_lat = lat2 - lat1
        a = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
        c = 2 * asin(sqrt(a))
        return 6367000 * c  # return distance in m


if __name__ == "__main__":
    from time import time

    # instantiate counter and parser and start parsing
    start = time()

    builder = GraphBuilder("./osm/luebeck.osm")

    parsed = time()

    builder.build_street_network()

    initialized = time()

    builder.find_node_categories()

    categorized = time()

    # noinspection PyProtectedMember
    paths, distances = builder.street_network.calculate_shortest_paths(1287690225)

    pathed = time()

    # done
    print("Time parsing OSM data: ", parsed - start, " seconds")
    print("Time initializing data structures: ", initialized - parsed, " seconds")
    print("Time finding node categories: ", categorized - initialized, " seconds")
    print("Time calculating shortest paths: ", pathed - categorized, " seconds")
    print("Nodes: ", len(builder.street_network.get_nodes()))
    print("Edges: ", len(builder.street_network.get_edges()))
    print("Residential Nodes: ", len(builder.residential_nodes))
    print("Residential Nodes connected to street network: ", len(builder.connected_residential_nodes))
    print("Industrial Nodes: ", len(builder.industrial_nodes))
    print("Industrial Nodes connected to street network: ", len(builder.connected_industrial_nodes))
    print("Commercial Nodes: ", len(builder.commercial_nodes))
    print("Commercial Nodes connected to street network: ", len(builder.connected_commercial_nodes))
