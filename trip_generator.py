from random import sample


def generate_trips(number_of_residents: int, potential_origins, potential_goals):
    """
    Distribute the residents over the potential_origins and set random goals (out of the potential_goals) for them.
    Args:
        number_of_residents: number of residents to be distributed -> number of trips to be generated
        potential_origins: potential origin nodes
        potential_goals: potential goal nodes

    Returns:
        A dict with the potential_origins as keys and lists of destinations / goals as the values. The total number
        of all destinations should be equal to the number_of_residents.
    """
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
