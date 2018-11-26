from collections import namedtuple

from pygraph.algorithms.minmax import shortest_path
from pygraph.classes.digraph import digraph


class StreetNetwork(object):
    """This class represents a street_id network"""

    STREET_ATTRIBUTE_INDEX = {
        "index"          : 0,  # duplicate word "INDEX" on purpose
        "length"         : 1,
        "max_speed"      : 2,
        "number_of_lanes": 3,
    }
    NODE_ATTRIBUTE_INDEX = {
        "longitude": 0,
        "latitude" : 1,
    }

    def __init__(self):
        # graph that holds the street network
        self._graph = digraph()
        self.bounds = None
        # give every street a sequential index (used for performance optimization)
        self.street_index = 0
        self.streets_by_index = dict()

    def has_street(self, street):
        return self._graph.has_edge(street)

    def add_street(self, street, length, max_speed, number_of_lanes=1):
        # attribute order is given through constants ATTRIBUTE_INDEX_...
        street_attributes = [self.street_index, length, max_speed, number_of_lanes]
        # set initial weight to ideal driving time
        driving_time = length / max_speed
        self._graph.add_edge(street, wt=driving_time, attrs=street_attributes)
        self.streets_by_index[self.street_index] = street

        self.street_index += 1

    def set_driving_time(self, street, driving_time):
        self._graph.set_edge_weight(street, driving_time)

    def get_driving_time(self, street):
        return self._graph.edge_weight(street)

    def get_street_index(self, street):
        return self._graph.edge_attributes(street)[StreetNetwork.STREET_ATTRIBUTE_INDEX['index']]

    def get_street_by_index(self, street_index):
        if street_index in self.streets_by_index:
            return self.streets_by_index[street_index]
        else:
            return None

    def change_max_speed(self, street, max_speed_delta):
        street_attributes = self._graph.edge_attributes(street)
        current_max_speed = street_attributes[StreetNetwork.STREET_ATTRIBUTE_INDEX['max_speed']]
        street_attributes[StreetNetwork.STREET_ATTRIBUTE_INDEX['max_speed']] = max(1, min(140,
                                                                                          current_max_speed +
                                                                                          max_speed_delta))

    def set_bounds(self, min_latitude, max_latitude, min_longitude, max_longitude):
        self.bounds = ((min_latitude, max_latitude), (min_longitude, max_longitude))

    def add_node(self, node, longitude, latitude):
        # attribute order is given through constants ATTRIBUTE_INDEX_...
        self._graph.add_node(node, [longitude, latitude])

    def get_nodes(self):
        return self._graph.nodes()

    def get_edges(self):
        return self._graph.edges()

    def node_coordinates(self, node):
        node_attributes = self._graph.node_attributes(node)

        return (node_attributes[StreetNetwork.NODE_ATTRIBUTE_INDEX['longitude']],
                node_attributes[StreetNetwork.NODE_ATTRIBUTE_INDEX['latitude']])

    def has_node(self, node):
        return self._graph.has_node(node)

    def calculate_shortest_paths(self, origin_node):
        return shortest_path(self._graph, origin_node)[0]

    _Street_Attributes = namedtuple("Street_Attributes", ["street", "index", "length", "max_speed", "number_of_lanes"])

    def get_street_attributes(self, street):
        street_attributes = self._graph.edge_attributes(street)
        return (street, street_attributes[StreetNetwork.STREET_ATTRIBUTE_INDEX['index']],
                street_attributes[StreetNetwork.STREET_ATTRIBUTE_INDEX['length']],
                street_attributes[StreetNetwork.STREET_ATTRIBUTE_INDEX['max_speed']],
                street_attributes[StreetNetwork.STREET_ATTRIBUTE_INDEX['number_of_lanes']])

    # iterator to iterate over the streets and their attributes
    def __iter__(self):
        for street in self._graph.edges():
            # get street attributes
            yield self.get_street_attributes(street)
