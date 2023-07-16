from yaml import load, dump, Loader
from traceback import format_exc

from config.configuration import Configuration


class ConfigurationProvider:

    def load(self, filename: str = "settings.yaml"):
        try:
            with open(f"./{filename}", mode="r+") as stream:
                config: dict = load(stream, Loader=Loader)
                return Configuration(config)
        except:
            print(
                f"Could not load configuration from external file {filename}\n{format_exc()}")
            return self._generate_default(filename)

    def _generate_default(self, filename: str = "settings.yaml"):
        default_confugration = {
            "log": {
                "file-path": "./",
                "level": 20,
                "file-name": "sample-application.log",
                "max-size-in-bytes": 100*1024*8,
                "max-part-size-in-bytes": 1024*1024*8
            },
            "db-name": "vacancies.db",
            "vacancy-limit": 100,
            "vacancy-prefetch": 50,
            "vacancy-search-query": "middle python developer",
            "hh-search-endpoint": "https://hh.ru/search/vacancy",
            "hh-api-endpoint": "https://api.hh.ru/vacancies",
            "hh-vacancy-details-endpoint": "https://hh.ru/vacancy/"
        }
        try:
            with open(f"./{filename}", "w") as stream:
                dump(default_confugration, stream)
            print(f"Default configuration was generated to {filename}")
            return Configuration(default_confugration)
        except:
            print(
                f"Could not generate default configuration\n{format_exc()}")
            pass


configuration: Configuration = ConfigurationProvider().load()
