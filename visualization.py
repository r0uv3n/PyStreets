import os
import re
from functools import partial

from PIL import Image, ImageChops, ImageDraw, ImageFont

import logger
from persistence import persist_read
from settings import settings
from simulation import calculate_driving_speed


class Visualization(object):
    """

    This class turns persistent traffic load data into images

    :param color_mode
    HEATMAP      - vary hue on a temperature-inspired scale from dark blue to red
    MONOCHROME   - vary brightness from black to white
    """
    ATTRIBUTE_KEY_COMPONENT = 2

    def __init__(self, name, color_mode='HEATMAP', log_callback=None):
        self.name = name
        self.renders_dir = f"{settings['renders_dir']}{self.name}/"
        self.persistent_files_dir = f"{settings['persistent_files_dir']}{self.name}/"
        self.logger = logger.init_logger(module="Visualization", name=self.name, log_callback=log_callback)
        self.persist_read = partial(persist_read, directory=self.persistent_files_dir)
        self.max_resolution = (15000, 15000)
        self.zoom = 1
        self.coord2km = (111.32, 66.4)  # distances between 2 deg of lat/lon
        self.bounds = None
        self.street_network = None
        self.node_coords = dict()
        self.color_mode = color_mode
        self.traffic_load_filename_expression = re.compile("^traffic_load_[0-9]+.pystreets$")

    def visualize(self, mode='TRAFFIC_LOAD'):
        self.logger.info("Finding files")
        all_files = os.listdir(self.persistent_files_dir)
        traffic_load_files = list(filter(self.traffic_load_filename_expression.search, all_files))

        self.logger.info("Reading street network")
        self.read_street_network(street_network_filename="street_network.pystreets")

        self.logger.debug("Finding maximum traffic load")
        max_load = 1
        for traffic_load_file in traffic_load_files:
            traffic_load = self.persist_read(traffic_load_file, is_array=True)
            for street, street_index, length, max_speed, number_of_lanes in self.street_network:
                max_load = max(max_load, traffic_load[street_index] / number_of_lanes)
        self.logger.debug(f"Maximum load is {max_load}")

        self.logger.info("Starting to draw traffic loads")
        step = 0
        while len(traffic_load_files) > 0:
            step += 1
            self.logger.info(f"Doing step nr {step}")

            # check if there is traffic load for the current step and draw it
            traffic_load_filename = f"traffic_load_{step}.pystreets"
            self.logger.debug(f"Traffic load filename is {traffic_load_filename}")
            if traffic_load_filename in traffic_load_files:
                self.logger.debug("Found traffic data")

                self.logger.info("Reading traffic load")
                traffic_load = self.persist_read(traffic_load_filename, is_array=True)

                self.logger.info("Drawing data")
                street_network_image: Image = self.draw(max_load, traffic_load, mode)
                self.logger.info(f"Saving image to disk \
                                 ({self.renders_dir}{mode.lower()}_{step}.png)")
                os.makedirs(os.path.dirname(self.renders_dir), exist_ok=True)
                street_network_image.save(f"{self.renders_dir}{mode.lower()}_{step}.png")

                traffic_load_files.remove(traffic_load_filename)

        self.logger.info("Done!")

    def draw(self, max_load: int, traffic_load: list, mode: str) -> Image:
        street_network_image = Image.new("RGBA", self.max_resolution, (0, 0, 0, 255))
        draw = ImageDraw.Draw(street_network_image)
        finished_streets = dict()
        for street, street_index, length, max_speed, number_of_lanes in self.street_network:
            width = 1  # max_speed / 50 looks bad for motorways
            value = 0
            current_traffic_load = traffic_load[street_index] / number_of_lanes
            if mode == 'TRAFFIC_LOAD':
                value = 1.0 * (current_traffic_load / max_load) ** (1 / 2)  # Sqrt for better visibility
            if mode == 'MAX_SPEED':
                value = min(1.0, 1.0 * max_speed / 140)
            if mode == 'IDEAL_SPEED':
                ideal_speed = calculate_driving_speed(length, max_speed, 0)
                value = min(1.0, 1.0 * ideal_speed / 140)
            if mode == 'ACTUAL_SPEED':
                actual_speed = calculate_driving_speed(length, max_speed, current_traffic_load)
                value = min(1.0, 1.0 * actual_speed / 140)
            if mode == "NUMBER_OF_LANES":
                value = min(1.0, number_of_lanes / 5)
            if frozenset(street) in finished_streets.keys():
                value += finished_streets[frozenset(street)]
            color = self.value_to_color(value)
            draw.line([self.node_coords[street[0]], self.node_coords[street[1]]],
                      fill=color, width=width)
            finished_streets[frozenset(street)] = value
        street_network_image = self.image_finalize(street_network_image, max_load, mode)
        return street_network_image

    def read_street_network(self, street_network_filename):
        self.street_network = self.persist_read(street_network_filename)
        self.bounds = self.street_network.bounds
        self.zoom = self.max_resolution[0] / max((self.bounds[0][1] - self.bounds[0][0]) * self.coord2km[0],
                                                 (self.bounds[1][1] - self.bounds[1][0]) * self.coord2km[1])
        for node in self.street_network.get_nodes():
            coords = self.street_network.node_coordinates(node)
            point = dict()
            for i in range(2):
                point[i] = (coords[i] - self.bounds[i][0]) * self.coord2km[i] * self.zoom
            self.node_coords[node] = (
                point[1], self.max_resolution[1] - point[0])  # x = longitude, y = latitude

    def value_to_color(self, value):
        value = min(1.0, max(0.0, value))
        if self.color_mode == 'MONOCHROME':
            brightness = min(255, int(15 + 240 * value))
            return brightness, brightness, brightness, 0
        if self.color_mode == 'HEATMAP':
            limit = 0
            if value <= limit:  # almost black to blue
                return "hsl(300,100%, 8%)"
            else:  # blue to red
                return "hsl(" + str(int(255 * (1 - (value - limit) / 1 - limit))) + ",100%," + str(
                        30 + 20 * value) + "%)"

    def image_finalize(self, street_network_image, max_load, mode):
        """
        :param mode
        TRAFFIC_LOAD - display absolute traffic load
        MAX_SPEED    - display local speed limits
        IDEAL_SPEED  - display calculated ideal speed based on safe breaking distance
        ACTUAL_SPEED - display calculated actual speed based on traffic load:
        """
        # take the current street network and make it pretty
        street_network_image = self.auto_crop(street_network_image)

        white = (255, 255, 255, 0)
        black = (0, 0, 0, 0)
        padding = self.max_resolution[0] // 40
        legend = Image.new("RGBA", street_network_image.size, (0, 0, 0, 255))
        font = ImageFont.load_default()
        draw = ImageDraw.Draw(legend)
        bar_outer_width = self.max_resolution[0] // 50
        bar_inner_width = min(bar_outer_width - 4, int(bar_outer_width * 0.85))
        # make sure the difference is a multiple of 4
        bar_inner_width = bar_inner_width - (bar_outer_width - bar_inner_width) % 4
        bar_offset = max(2, (bar_outer_width - bar_inner_width) // 2)

        if mode in ['TRAFFIC_LOAD', 'MAX_SPEED', 'IDEAL_SPEED', 'ACTUAL_SPEED', 'NUMBER_OF_LANES']:
            draw.rectangle([(0, 0), (bar_outer_width, legend.size[1] - 1)], fill=white)
            border_width = int(bar_offset / 2)
            draw.rectangle(
                    [(border_width, border_width), (bar_outer_width - border_width, legend.size[1] - 1 - border_width)],
                    fill=black)
            for y in range(bar_offset, legend.size[1] - bar_offset):
                value = 1.0 * (y - bar_offset) / (legend.size[1] - 2 * bar_offset)
                color = self.value_to_color(1.0 - value)  # highest value at the top
                draw.line([(bar_offset, y), (bar_offset + bar_inner_width, y)], fill=color)
            if mode == 'TRAFFIC_LOAD':
                top_text = str(round(max_load, 1)) + " cars gone through per lane"
                bottom_text = "0 cars gone through"
            elif mode == 'MAX_SPEED':
                top_text = "speed limit: 140 km/h or higher"
                bottom_text = "speed limit: 0 km/h"
            elif mode == 'IDEAL_SPEED':
                top_text = "ideal driving speed: 140 km/h or higher"
                bottom_text = "ideal driving speed: 0 km/h"
            elif mode == 'ACTUAL_SPEED':
                top_text = "actual driving speed: 140 km/h or higher"
                bottom_text = "actual driving speed: 0 km/h"
            elif mode == "NUMBER_OF_LANES":
                top_text = "5 lanes"
                bottom_text = "0 lanes"
            else:
                raise ValueError("mode is not one of 'TRAFFIC_LOAD', 'MAX_SPEED', 'IDEAL_SPEED', 'ACTUAL_SPEED' or "
                                 "'NUMBER_OF_LANES'")
            draw.text((int(bar_outer_width * 1.3), 0), top_text, font=font, fill=white)
            box = draw.textsize(bottom_text, font=font)
            draw.text((int(bar_outer_width * 1.3), legend.size[1] - box[1]), bottom_text, font=font, fill=white)

        legend = self.auto_crop(legend)

        copyright_text = "Generated using data from the OpenStreetMap project."
        copyright_size = draw.textsize(copyright_text, font=font)

        final_width = street_network_image.size[0] + legend.size[0] + 3 * padding
        final_height = legend.size[1] + 2 * padding + copyright_size[1] + 1
        final = Image.new("RGB", (final_width, final_height), black)
        final.paste(street_network_image, (padding, padding))
        final.paste(legend, (street_network_image.size[0] + 2 * padding, padding))
        ImageDraw.Draw(final).text((2, legend.size[1] + 2 * padding), copyright_text, font=font, fill=white)
        return final

    @staticmethod
    def auto_crop(image):
        # remove black edges from image
        empty = Image.new("RGBA", image.size, (0, 0, 0))
        difference = ImageChops.difference(image, empty)
        bbox = difference.getbbox()
        return image.crop(bbox)


if __name__ == "__main__":
    visualization = Visualization(name="Lübeck Klein Variation")
    visualization.visualize(mode="TRAFFIC_LOAD")
