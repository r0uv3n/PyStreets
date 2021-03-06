settings = {
    # technical settings
    "renders_dir"                      : "./renders/",
    "persistent_files_dir"             : "./persistent files/",
    "osm_dir"                          : "./osm/",
    "random_seed"                      : None,  # set to None to use system time

    # logging
    "logs_dir"                         : "./logs/",
    "logging_level"                    : "DEBUG",

    # simulation settings
    "max_simulation_steps"             : 4,
    "number_of_residents"              : 1000,
    "use_attributed_nodes"             : True,

    # period over which the traffic is distributed (24h = the hole day)
    "traffic_period_duration"          : 2,  # h
    "car_length"                       : 4,  # m
    "min_breaking_distance"            : 0.001,  # m
    "jam_tolerance"                    : 0.5,
    # take breaking deceleration for asphalt
    # see http://www.bense-jessen.de/Infos/Page10430/page10430.html
    "braking_deceleration"             : 7.5,  # m/s²
    "steps_between_street_construction": 10,
    "trip_volume"                      : 1,

    # visualization settings
    "zoom"                             : 1,
    "max_resolution"                   : (15000, 15000),
}
