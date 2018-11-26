from functools import partial
from random import random, seed

import logger
from osmdata import GraphBuilder
from persistence import persist_write, persist_read
from settings import settings
from simulation import Simulation
from tripgenerator import generate_trips


class PyStreets(object):
    """This class runs the Streets program."""

    def __init__(self, existing_data=None, existing_network=None, name="PyStreets"):
        self.name = name
        # set up logging
        self.logger = logger.init_logger(module=None, name=self.name, log_callback=None)
        self.logger.info("Logging initialized")

        self.logger.info("Setting up persistence")
        self.persist_write = partial(persist_write, sub_dir=f"{self.name}/")
        self.persist_read = partial(persist_read, sub_dir=f"{self.name}/")

        self.logger.info("Initializing PyStreets")

        # set random seed based on process rank
        self.logger.info("Generating random seed")
        random_seed = settings["random_seed"]
        seed(random_seed)
        if existing_network is None:
            self.logger.info("Reading OpenStreetMap data")
            self.data = GraphBuilder(settings["osm_file"])

            self.logger.info("Building street network")
            self.street_network = self.data.build_street_network()

            self.logger.info("Locating area types")
            self.data.find_node_categories()

            self.logger.info("Saving OpenStreetMap data to disk")
            self.persist_write(filename="data.pystreets", data=self.data)

            self.logger.info("Saving street network to disk")
            self.persist_write("/street_network.pystreets", self.street_network)
        else:
            self.logger.info("Reading existing OpenStreetMap data from disk")
            self.data = self.persist_read(existing_data)

            self.logger.info("Reading existing street network from disk")
            self.street_network = self.persist_read(existing_network)

    def run(self):
        self.logger.info("Generating test_trips")
        number_of_residents = settings["number_of_residents"]
        if settings["use_attributed_nodes"]:
            potential_origins = self.data.connected_residential_nodes
            potential_goals = self.data.connected_commercial_nodes | self.data.connected_industrial_nodes
        else:
            potential_origins = self.street_network.get_nodes()
            potential_goals = self.street_network.get_nodes()
        trips = generate_trips(number_of_residents, potential_origins, potential_goals)

        # set traffic jam tolerance for this process and its test_trips
        if settings['jam_tolerance'] is None:
            jam_tolerance = random()
        else:
            jam_tolerance = settings['jam_tolerance']
        self.logger.info(f"Setting traffic jam tolerance to {round(jam_tolerance, 2)}")

        # run simulation
        simulation = Simulation(street_network=self.street_network, trips=trips,
                                jam_tolerance=jam_tolerance, name=self.name, log_callback=self.logger)

        for step in range(settings["max_simulation_steps"]):

            if step > 0 and step % settings["steps_between_street_construction"] == 0:
                self.logger.info("Road construction taking place")
                simulation.road_construction()
                if settings["persist_traffic_load"]:
                    self.persist_write(f"street_network_{step + 1}.pystreets", simulation.street_network)

            self.logger.info(f"Running simulation step {step + 1} of {settings['max_simulation_steps']} ")
            simulation.step()
            self.logger.info("Saving traffic load to disk")
            self.persist_write(f"traffic_load_{step + 1}.pystreets", simulation.traffic_load, is_array=True)
        self.logger.info("Done!")


if __name__ == "__main__":
    instance_name = "PyStreets"
    if settings['reuse_data']:
        MainSim = PyStreets(existing_data=None, existing_network=None, name=instance_name)
    else:
        MainSim = PyStreets(existing_data=None, existing_network=None, name=instance_name)
    MainSim.run()
