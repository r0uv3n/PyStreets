from functools import partial
from random import random, seed

import logger
from osm_data import GraphBuilder
from persistence import persist_write, persist_read
from settings import settings
from simulation import Simulation
from trip_generator import generate_trips
from visualization import Visualization


class PyStreets(object):
    """"Loads data, simulates and visualizes traffic.

    Attributes:
        name:
        osm_filename: Filename of the .osm file to be used, which should be located in the osm_dir given in
        settings.py. Not necessary if existing_data is True
        existing_data: Path of an existing data.pystreets file to be used instead of data newly extracted from a .osm
        file. If not None, significantly reduces startup time.
        existing_network: Path of an existing street_network.pystreets file. Does not do anything if existing_data is
        None
        visualize_mode: 4 options:
    TRAFFIC_LOAD - Display absolute traffic load.
    MAX_SPEED    - Display local speed limits.
    IDEAL_SPEED  - Display calculated ideal speed based on safe breaking distance.
    ACTUAL_SPEED - Display calculated actual speed based on traffic load.
        color_mode: 2 options:
    HEATMAP      - Vary hue on a temperature-inspired scale from dark blue to red.
    MONOCHROME   - Vary brightness from black to white.
        """

    def __init__(self, name, osm_filename=None, existing_data=None, existing_network=None,
                 visualize_mode="TRAFFIC_LOAD",
                 color_mode="HEATMAP"):
        self.name = name

        # set up logging
        self.logger = logger.init_logger(module="PyStreets", name=self.name, log_callback=None)
        self.logger.setLevel(settings["logging_level"])
        self.logger.info("Logging for PyStreets initialized")

        self.persistent_files_dir = f"{settings['persistent_files_dir']}{self.name}/"
        self.logger.debug(f"Persistent files directory is {self.persistent_files_dir}")

        self.logger.info("Setting up persistence")
        self.persist_write = partial(persist_write, directory=self.persistent_files_dir)
        self.persist_read = partial(persist_read, directory=self.persistent_files_dir)

        self.logger.info("Initializing PyStreets")

        self.logger.info("Generating random seed")
        random_seed = settings["random_seed"]
        seed(random_seed)
        if existing_data is None:
            self.logger.info("Reading OpenStreetMap data")
            self.data = GraphBuilder(settings["osm_dir"] + osm_filename, name=self.name, log_callback=self.logger)

            self.logger.info("Getting street network")
            self.street_network = self.data.street_network

            self.logger.info("Saving OpenStreetMap data to disk")
            self.persist_write(filename=f"data.pystreets", data=self.data)

            self.logger.info("Saving street network to disk")
            self.persist_write(f"street_network.pystreets", self.street_network)
        else:
            self.logger.info("Reading existing OpenStreetMap data from disk")
            self.data = self.persist_read(existing_data)

            self.logger.info("Reading existing street network from disk")
            self.street_network = self.persist_read(existing_network)

        self.visualization = Visualization(name=self.name, mode=visualize_mode, color_mode=color_mode,
                                           street_network=self.street_network, log_callback=self.logger)
        assert self.visualization.persistent_files_dir == self.persistent_files_dir

    def run(self, visualize=True):
        """

        Args:
            visualize: If True, generates and saves Visualizations of the traffic load according to the settings in
            self.visualization

        Returns:
            None
        """
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
        self.logger.info(f"Set traffic jam tolerance to {round(jam_tolerance, 2)}")

        self.logger.info("Running Simulation")
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
        self.logger.info("Simulation complete")
        if visualize:
            self.logger.info("Starting visualization")
            self.visualization.visualize()
            self.logger.info("Visualization complete")
        self.logger.info("Done!")


if __name__ == "__main__":
    instance_name = "luebeck_zentrum.osm"
    visualization_mode = "TRAFFIC_LOAD"  # "TRAFFIC_LOAD", "IDEAL_SPEED", "ACTUAL_SPEED", "MAX_SPEED" - check docstrings
    MainSim = PyStreets(osm_filename="luebeck_klein_1.osm", existing_data=None,
                        existing_network=None, name="Lübeck Klein Variation", visualize_mode=visualization_mode)
    MainSim.run()
