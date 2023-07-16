
from logging import Logger, getLogger, Formatter, StreamHandler
from logging.handlers import RotatingFileHandler
from sys import stdout
from time import time
from typing import Callable
from config.provider import configuration


def time_and_log(method: Callable):
    def wrapper(*args, **kwargs):
        current_ts = time()
        result = method(*args, **kwargs)
        tooks = time() - current_ts
        log = logger(method.__name__)
        log.info(f"Method invokation {method.__name__} tooks {tooks} seconds")
        return result
    return wrapper


def logger(name: str) -> Logger:
    logger = getLogger(name)
    logger.setLevel(configuration.property("log.level", 20))
    logger.addHandler(default_log_handler)
    logger.addHandler(default_log_file_handler)
    return logger


default_log_formatter: Formatter = Formatter(
    fmt="%(asctime)s: [%(levelname)s] [%(processName)-10s] [%(threadName)s] [%(name)s]\t-\t%(message)s")
default_log_handler: StreamHandler = StreamHandler(stream=stdout)
default_log_handler.setFormatter(default_log_formatter)

log_max_part_size_in_bytes = configuration.property(
    "log.max-part-size-in-bytes", 100*1024*8)
log_max_size_in_bytes = configuration.property(
    "log.max-size-in-bytes", 1024*1024*8)
log_file_path = configuration.property("log.file-path", "./")
log_file_name = configuration.property("log.file-name", "application.log")

default_log_file_handler: StreamHandler = RotatingFileHandler(filename=f'{log_file_path}/{log_file_name}',
                                                              mode="w", maxBytes=log_max_part_size_in_bytes,
                                                              backupCount=round(log_max_size_in_bytes/log_max_part_size_in_bytes))
default_log_file_handler.setFormatter(default_log_formatter)
