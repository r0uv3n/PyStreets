from array import array
from itertools import repeat
from math import sqrt

import logger
from settings import settings
from street_network import StreetNetwork


class Simulation(object):
    """This class does the actual simulation steps"""

    # noinspection PyShadowingNames
    def __init__(self, street_network, trips, jam_tolerance,
                 name="PyStreets", log_callback=None):
        self.name = name
        self.logger = logger.init_logger(module="Simulation", name=self.name, log_callback=log_callback)
        self.street_network = street_network
        self.trips = trips
        self.jam_tolerance = jam_tolerance
        self.step_counter = 0
        self.traffic_load = array("I", repeat(0, self.street_network.street_index))

        self.cumulative_traffic_load = None

    def step(self):
        self.step_counter += 1
        self.logger.info("Preparing edges...")

        # update driving time based on traffic load
        for street, street_index, length, max_speed, number_of_lanes in self.street_network:
            street_traffic_load = self.traffic_load[street_index]

            # ideal speed is when the street is empty
            ideal_speed = calculate_driving_speed(length, max_speed, 0, number_of_lanes)
            # actual speed may be less then that
            actual_speed = calculate_driving_speed(length, max_speed, street_traffic_load, number_of_lanes)
            # based on traffic jam tolerance the deceleration is weighted differently
            perceived_speed = actual_speed + (ideal_speed - actual_speed) * self.jam_tolerance

            driving_time = length / perceived_speed

            self.street_network.set_driving_time(street, driving_time)

        self.logger.info("Resetting traffic load...")
        self.traffic_load = array("I", repeat(0, self.street_network.street_index))

        self.logger.info("Processing trips...")
        goal_nr = 0
        for origin_nr, origin in enumerate(self.trips.keys()):
            # calculate all shortest paths from resident to every other node
            self.logger.spam(f"Origin nr {origin_nr}...")
            paths = self.street_network.calculate_shortest_paths(origin)
            # increase traffic load
            for goal in self.trips[origin]:
                # is the goal even reachable at all? if not, ignore for now
                if goal in paths:
                    # hop along the edges until we're there
                    goal_nr += 1
                    current = goal
                    while current != origin:
                        street = (min(current, paths[current]), max(current, paths[current]))
                        current = paths[current]
                        usage = settings["trip_volume"]
                        street_index = self.street_network.get_street_index(street)
                        self.traffic_load[street_index] += usage
        self.logger.info(f"Successfully processed {len(self.trips)} origins and {goal_nr} goals")


def calculate_driving_speed(street_length, max_speed, number_of_trips, number_of_lanes=1):
    # distribute test_trips over the street
    available_space_for_each_car = street_length * number_of_lanes / max(number_of_trips, number_of_lanes)  # m
    available_braking_distance = max(available_space_for_each_car - settings["car_length"],
                                     settings["min_breaking_distance"])  # m
    # how fast can a car drive to ensure the calculated breaking distance?
    potential_speed = sqrt(settings["braking_deceleration"] * available_braking_distance * 2)  # m/s
    # cars respect speed limit
    actual_speed = min(max_speed, potential_speed * 3.6)  # km/h

    return actual_speed


if __name__ == "__main__":
    def out(*output):
        for o in output:
            print(o),
        print('')


    street_network = StreetNetwork()
    street_network.add_node(1, 0, 0)
    street_network.add_node(2, 0, 0)
    street_network.add_node(3, 0, 0)
    street_network.add_street((1, 2,), 10, 50)
    street_network.add_street((2, 3,), 100, 140)

    trips = dict()
    trips[1] = [3]

    sim = Simulation(street_network, trips, 0.6, "PyStreets", out)
    for step in range(10):
        print("Running simulation step", step + 1, "of 10...")
        sim.step()
    print("Done!")
