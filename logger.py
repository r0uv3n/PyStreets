import inspect
import logging

from settings import settings


class ActionFilter(logging.Filter):
    """Adds the currently running method to the record"""
    def filter(self, record):
        """Adds the currently running method to the record"""
        record.action = inspect.stack()[5][3]
        return True


def init_logger(name="PyStreets", module: str = None, log_callback: logging.Logger = None):
    if log_callback is None:
        format_str = '%(asctime)s - %(name)s - %(levelname)s - %(action)s - %(message)s'
        level = logging.DEBUG

        # mainly for anything not pystreets.py
        if module is not None:
            logging.basicConfig(
                    filename=f"{settings['logs_dir']}{name}_{module}.log",
                    level=level,
                    format=format_str)
            logger = logging.getLogger(f"{name} {module}")

        # mainly for pystreets.py
        else:
            logging.basicConfig(
                    filename=f"{settings['logs_dir']}{name}.log",
                    level=level,
                    format=format_str)
            logger = logging.getLogger(name)
    else:
        logger = log_callback.getChild(module)
    add_action = ActionFilter()
    logger.addFilter(add_action)
    return logger
