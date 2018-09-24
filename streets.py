#!/usr/bin/env python
# -*- coding: utf-8 -*
from random import random, seed

from osmdata import GraphBuilder
from persistence import persist_write, persist_read
from settings import settings
from simulation import Simulation
from tripgenerator import generate_trips


class PyStreets(object):
    """This class runs the Streets program."""

    def __init__(self, existing_data=None, existing_network=None):
        self.log("Welcome to PyStreets!")
        # set random seed based on process rank
        random_seed = settings["random_seed"]
        seed(random_seed)
        if existing_network is None:
            self.log("Reading OpenStreetMap data...")
            data = GraphBuilder(settings["osm_file"])

            self.log("Building street network...")
            street_network = data.build_street_network()

            self.log("Locating area types...")
            data.find_node_categories()

            self.log("Saving OpenStreetMap data to disk...")
            persist_write(filename="data.pystreets", data=data)

            self.log_indent("Saving street network to disk...")
            persist_write("/street_network.pystreets", street_network)

        else:
            self.log("Reading existing OpenStreetMap data from disk...")
            data = persist_read(filename=existing_data)

            self.log("Reading existing street network from disk...")
            street_network = persist_read(existing_network)

        self.log("Generating test_trips...")
        number_of_residents = settings["number_of_residents"]
        if settings["use_attributed_nodes"]:
            potential_origins = data.connected_residential_nodes
            potential_goals = data.connected_commercial_nodes | data.connected_industrial_nodes
        else:
            potential_origins = street_network.get_nodes()
            potential_goals = street_network.get_nodes()
        trips = generate_trips(number_of_residents, potential_origins, potential_goals)
        # set traffic jam tolerance for this process and its test_trips
        jam_tolerance = random()
        self.log("Setting traffic jam tolerance to", str(round(jam_tolerance, 2)) + "...")

        # run simulation
        simulation = Simulation(street_network, trips, jam_tolerance, self.log_indent)

        for step in range(settings["max_simulation_steps"]):

            if step > 0 and step % settings["steps_between_street_construction"] == 0:
                self.log_indent("Road construction taking place...")
                simulation.road_construction()
                if settings["persist_traffic_load"]:
                    persist_write("street_network_" + str(step + 1) + ".pystreets", simulation.street_network)

            self.log("Running simulation step", step + 1, "of", str(settings["max_simulation_steps"]) + "...")
            simulation.step()
            self.log_indent("Saving traffic load to disk...")
            persist_write("traffic_load_" + str(step + 1) + ".pystreets", simulation.traffic_load, is_array=True)
        self.log("Done!")

    @staticmethod
    def log(*output):
        if settings["logging"] == "stdout":
            print(*output)

    @staticmethod
    def log_indent(*output):
        if settings["logging"] == "stdout":
            print("   ", *output)


if __name__ == "__main__":
    if settings['reuse_data']:
        PyStreets(existing_data="data.pystreets", existing_network="street_network.pystreets")
    else:
        PyStreets(existing_data=None, existing_network=None)
