from typing import Generator, List, Self, Tuple


class DataContainer(dict):

    def get(self, key):
        value = self._get_property_internal(key)
        return value

    def get(self, key, default=None):
        value = self._get_property_internal(key)
        return value if value else default

    def _get_property_internal(self, name: str) -> any:
        parts: List[str] = name.split(".")
        value: any = self
        for part in parts:
            try:
                value = value.__getitem__(part)
            except KeyError:
                return None

            if value and isinstance(value, dict):
                continue
            else:
                break

        return value

    def __getitem__(self, __key: any) -> any:
        value = None
        try:
            value = super().__getitem__(__key)
        except KeyError:
            try:
                value = self.__getattribute__(__key)
            except AttributeError:
                pass

        return value


class Configuration(DataContainer):

    def __init__(self, config: dict):
        super().__init__(config if config else {})

    def each(self, name: str) -> Generator[Tuple[str, Self], None, None]:
        values = self._get_property_internal(name) if name else self
        if isinstance(values, list):
            for index, value in enumerate(values):
                if isinstance(value, dict):
                    yield (str(index), Configuration(value))

        if isinstance(values, dict):
            for k in values.keys():
                value = values.get(k)
                if isinstance(value, dict):
                    yield (k, Configuration(value))

    def property(self, name: str, default: any = None) -> any:
        return self.get(name, default)
