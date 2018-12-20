from random import sample


def generate_trips(number_of_residents, potential_origins, potential_goals):
    """This class creates the appropriate number of residents and manages the test_trips"""
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
