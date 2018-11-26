import inspect
import logging

from settings import settings


class ActionFilter(logging.Filter):
    """Adds the currently running method to the record"""
    def filter(self, record):
        """Adds the currently running method to the record"""
        record.action = inspect.stack()[5][3]
        return True


def init_logger(name, module: str = None, log_callback: logging.Logger = None):
    if log_callback is None:
        logging.basicConfig(
                filename=f"{settings['logs_dir']}{name} {module}.log",
                level=logging.DEBUG,
                format='%(asctime)s - %(name)s - %(levelname)s - %(action)s - %(message)s')

        logger = logging.getLogger(module)
    else:
        logger = log_callback.getChild(module)
    add_action = ActionFilter()
    logger.addFilter(add_action)
    return logger
