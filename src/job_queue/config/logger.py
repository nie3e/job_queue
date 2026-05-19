import logging

logger = logging.getLogger("worker")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter(
    fmt="[%(asctime)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S")
)
logger.addHandler(ch)