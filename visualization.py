import os
import re
from functools import partial
from logging import Logger # for typing

from PIL import Image, ImageChops, ImageDraw, ImageFont

import logger
from persistence import persist_read
from settings import settings
from simulation import calculate_driving_speed
from street_network import StreetNetwork # for typing


class Visualization(object):
    """
    This class turns persistent traffic load data into images

    Attributes:
      name: Determines renders_dir and is used for logging
      mode: 4 options:
    TRAFFIC_LOAD - Display absolute traffic load.
    MAX_SPEED    - Display local speed limits.
    IDEAL_SPEED  - Display calculated ideal speed based on safe breaking distance.
    ACTUAL_SPEED - Display calculated actual speed based on traffic load.
      color_mode: 2 options:
    HEATMAP      - Vary hue on a temperature-inspired scale from dark blue to red.
    MONOCHROME   - Vary brightness from black to white.
      street_network: StreetNetwork to operate on, if None, read from persistent_dir.
      log_callback: Parent Logger; If None, logs to a new file.
      renders_dir: Directory in which ".png"s are saved.
    """
    ATTRIBUTE_KEY_COMPONENT = 2
    coord2km = (111.32, 66.4)  # distances between 2 deg of lat/lon

    def __init__(self, name: str, mode: str = "Traffic_Load", color_mode="HEATMAP",
                 street_network: StreetNetwork = None, log_callback: Logger = None, renders_dir: str = None):
        self.name = name
        self.mode = mode
        self.color_mode = color_mode

        self.logger = logger.init_logger(module="Visualization", name=self.name, log_callback=log_callback)
        self.logger.info("Logging for Visualization initialized")

        self.renders_dir = renders_dir if renders_dir is not None else f"{settings['renders_dir']}{self.name}/"
        self.persistent_files_dir = f"{settings['persistent_files_dir']}{self.name}/"
        self.persist_read = partial(persist_read, directory=self.persistent_files_dir)
        self.traffic_load_filename_expression = re.compile("^traffic_load_[0-9]+.pystreets$")

        self.max_resolution = settings['max_resolution']
        self.zoom = settings['zoom']

        self.node_coords = dict()

        self.street_network = street_network


    @property
    def street_network(self) -> StreetNetwork:
        return self._street_network

    @street_network.setter
    def street_network(self, value: StreetNetwork):
        self._street_network = value
        self.bounds = self.street_network.bounds
        self.zoom = self.max_resolution[0] / max((self.bounds[0][1] - self.bounds[0][0]) * self.coord2km[0],
                                                 (self.bounds[1][1] - self.bounds[1][0]) * self.coord2km[1])

        self.node_coords = dict()
        for node in self.street_network.get_nodes():
            coords = self.street_network.node_coordinates(node)
            point = dict()
            for i in range(2):
                point[i] = (coords[i] - self.bounds[i][0]) * self.coord2km[i] * self.zoom
            self.node_coords[node] = (point[1], self.max_resolution[1] - point[0])  # x = longitude, y = latitude

    @property
    def mode(self):
        """
        TRAFFIC_LOAD - Display absolute traffic load.
        MAX_SPEED    - Display local speed limits.
        IDEAL_SPEED  - Display calculated ideal speed based on safe breaking distance.
        ACTUAL_SPEED - Display calculated actual speed based on traffic load.

        Args:

        Returns:
          : The currently selected mode.

        """
        return self._mode

    @mode.setter
    def mode(self, value: str):
        value = value.upper()  # accept input independent of case
        possible_modes = ("TRAFFIC_LOAD", "MAX_SPEED", "IDEAL_SPEED", "ACTUAL_SPEED")
        if value not in possible_modes:
            raise ValueError(f"Value must be one of {possible_modes}")
        self._mode = value

    @property
    def color_mode(self):
        """
        HEATMAP      - Vary hue on a temperature-inspired scale from dark blue to red.
        MONOCHROME   - Vary brightness from black to white.

        Returns:
          : The currently selected color_mode.

        """
        return self._color_mode

    @color_mode.setter
    def color_mode(self, value):
        value = value.upper()
        possible_color_modes = ("MONOCHROME", "HEATMAP")
        if value not in possible_color_modes:
            raise ValueError(f"Value must be one of {possible_color_modes}")
        self._color_mode = value

    def visualize(self):
        self.logger.info("Finding files")
        all_files = os.listdir(self.persistent_files_dir)
        traffic_load_files = list(filter(self.traffic_load_filename_expression.search, all_files))

        self.logger.info("Reading street network")
        self.street_network = self.persist_read("street_network.pystreets")

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
                street_network_image: Image = self.draw(max_load, traffic_load)
                self.logger.info(f"Saving image to disk \
                                 ({self.renders_dir}{self.mode.lower()}_{step}.png)")
                os.makedirs(os.path.dirname(self.renders_dir), exist_ok=True)
                street_network_image.save(f"{self.renders_dir}{self.mode.lower()}_{step}.png")

                traffic_load_files.remove(traffic_load_filename)

        self.logger.info("Done!")

    def draw(self, max_load: int, traffic_load: list) -> Image:
        street_network_image = Image.new("RGBA", self.max_resolution, (0, 0, 0, 255))
        draw = ImageDraw.Draw(street_network_image)
        finished_streets = dict()
        for street, street_index, length, max_speed, number_of_lanes in self.street_network:
            width = 1  # max_speed / 50 looks bad for motorways
            value = 0
            current_traffic_load = traffic_load[street_index] / number_of_lanes
            if self.mode == 'TRAFFIC_LOAD':
                value = 1.0 * (current_traffic_load / max_load) ** (1 / 2)  # Sqrt for better visibility
            if self.mode == 'MAX_SPEED':
                value = min(1.0, 1.0 * max_speed / 140)
            if self.mode == 'IDEAL_SPEED':
                ideal_speed = calculate_driving_speed(length, max_speed, 0)
                value = min(1.0, 1.0 * ideal_speed / 140)
            if self.mode == 'ACTUAL_SPEED':
                actual_speed = calculate_driving_speed(length, max_speed, current_traffic_load)
                value = min(1.0, 1.0 * actual_speed / 140)
            if self.mode == "NUMBER_OF_LANES":
                value = min(1.0, number_of_lanes / 5)
            if frozenset(street) in finished_streets.keys():
                value += finished_streets[frozenset(street)]
            color = self.value_to_color(value)
            draw.line([self.node_coords[street[0]], self.node_coords[street[1]]], fill=color, width=width)
            finished_streets[frozenset(street)] = value

        self.logger.info("Finalizing Image")
        street_network_image = self._image_finalize(street_network_image, max_load)
        return street_network_image

    def value_to_color(self, value: float):
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

    def _image_finalize(self, street_network_image: Image, max_load: int) -> Image:
        """
        Take the current street network and make it pretty. Crop, add legend and disclaimer, that the source of all
        data is OpenStreetMaps.

        Args:
          street_network_image: Image:
          max_load: int:

        Returns:
            Pretty PIL.Image version of the street_network_image
        """
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

        if self.mode in ['TRAFFIC_LOAD', 'MAX_SPEED', 'IDEAL_SPEED', 'ACTUAL_SPEED', 'NUMBER_OF_LANES']:
            draw.rectangle([(0, 0), (bar_outer_width, legend.size[1] - 1)], fill=white)
            border_width = int(bar_offset / 2)
            draw.rectangle(
                    [(border_width, border_width), (bar_outer_width - border_width, legend.size[1] - 1 - border_width)],
                    fill=black)
            for y in range(bar_offset, legend.size[1] - bar_offset):
                value = 1.0 * (y - bar_offset) / (legend.size[1] - 2 * bar_offset)
                color = self.value_to_color(1.0 - value)  # highest value at the top
                draw.line([(bar_offset, y), (bar_offset + bar_inner_width, y)], fill=color)
            if self.mode == 'TRAFFIC_LOAD':
                top_text = str(round(max_load, 1)) + " cars gone through per lane"
                bottom_text = "0 cars gone through"
            elif self.mode == 'MAX_SPEED':
                top_text = "speed limit: 140 km/h or higher"
                bottom_text = "speed limit: 0 km/h"
            elif self.mode == 'IDEAL_SPEED':
                top_text = "ideal driving speed: 140 km/h or higher"
                bottom_text = "ideal driving speed: 0 km/h"
            elif self.mode == 'ACTUAL_SPEED':
                top_text = "actual driving speed: 140 km/h or higher"
                bottom_text = "actual driving speed: 0 km/h"
            elif self.mode == "NUMBER_OF_LANES":
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
    def auto_crop(image: Image) -> Image:
        """
        Remove black edges from image

        Args:
          image: PIL.Image to be cropped

        Returns:
            Cropped version of the given Image
        """
        empty = Image.new("RGBA", image.size, (0, 0, 0))
        difference = ImageChops.difference(image, empty)
        bbox = difference.getbbox()
        return image.crop(bbox)


if __name__ == "__main__":
    visualization = Visualization(name="Lübeck Klein Variation")
    visualization.mode = "TRAFFIC_LOAD"
    visualization.visualize()
