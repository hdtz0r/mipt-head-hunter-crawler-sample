from asyncio import sleep
from time import time, sleep as sync_sleep
from typing import Callable, List

from logging_utils import logger

log = logger(__name__)


class Backoff:

    _delay: float
    _timestamp: int

    def __init__(self, delay_in_seconds: float) -> None:
        self._delay = delay_in_seconds
        self._timestamp = time()

    def set(self):
        self._timestamp = time()

    def is_expired(self) -> bool:
        return time() > self._timestamp + self._delay


def async_retry(errors: List[Exception], backoff=Backoff(10)):
    def _retry_wrapper(f: Callable):
        async def _enclosed_function(*args: any, **kwargs: any) -> any:
            while True:
                if backoff.is_expired():
                    try:
                        return await f(*args, **kwargs)
                    except Exception as ex:
                        should_continue = False
                        for error in errors:
                            if isinstance(ex, error):
                                backoff.set()
                                await sleep(backoff._delay)
                                log.warn("Retrying call of %s %s",
                                         callable.__name__, str(ex))
                                should_continue = True
                                break
                        if not should_continue:
                            raise
                else:
                    await sleep(0.01)
        return _enclosed_function
    return _retry_wrapper


def retry(errors: List[Exception], backoff=Backoff(10)):
    def _retry_wrapper(f: Callable):
        def _enclosed_function(*args: any, **kwargs: any) -> any:
            while True:
                if backoff.is_expired():
                    try:
                        return f(*args, **kwargs)
                    except Exception as ex:
                        should_continue = False
                        for error in errors:
                            if isinstance(ex, error):
                                backoff.set()
                                sync_sleep(backoff._delay)
                                log.warn("Retrying call of %s %s",
                                         callable.__name__, str(ex))
                                should_continue = True
                                break
                        if not should_continue:
                            raise
                else:
                    sync_sleep(0.01)
        return _enclosed_function
    return _retry_wrapper
