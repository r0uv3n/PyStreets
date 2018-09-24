#!/usr/bin/env python
# -*- coding: utf-8 -*
from random import sample
from time import time


# This class creates the appropriate number of residents and manages the test_trips
def generate_trips(number_of_residents, potential_origins, potential_goals):
    trips = dict()
    number_of_goals = 0
    for i in range(0, number_of_residents):
        origin = sample(potential_origins, 1)[0]
        goal = sample(potential_goals, 1)[0]

        if origin in trips.keys():
            goals = trips[origin]
        else:
            goals = list()
        goals.append(goal)
        number_of_goals += 1
        trips[origin] = goals
    assert number_of_goals == number_of_residents
    return trips


if __name__ == "__main__":
    start = time()

    test_trips = generate_trips(30, {1, 2, 3, 4, 5}, {6, 7, 8, 9, 10})

    generated = time()

    # done
    print("Trips: ", test_trips)
    print("Time generating test_trips: ", generated - start, " seconds")
