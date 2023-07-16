import argparse
import asyncio
from logging_utils import logger, time_and_log
from provider.hh_dataprovider import each_vacancy
from datastore.sqlite_datastore import save_all, initialize

from config.provider import configuration

log = logger(__name__)


async def main(use_api: bool):
    vacancies = []
    try:
        async for vacancy in each_vacancy(configuration.property("vacancy-search-query", "middle python developer"),
                                         configuration.property(
                "vacancy-limit", 100),
                configuration.property(
                "vacancy-prefetch", 50),
                use_api):
            vacancies.append(vacancy)
        log.info("Fetched total %s vacancies", len(vacancies))
        try:
            save_all(vacancies)
        except Exception as ex:
            log.error("Could not persist vacancies", ex)
    except Exception as ex:
        log.error("Could not fetch vacancies cause", ex)


@time_and_log
def app_runner():
    parser = argparse.ArgumentParser(
        prog='HeadHunter Vacancy Parser',
        description='The program will parse vancancies and saves it to the datastore using api or html crawlers')
    parser.add_argument('-api', '--useapi', action='store_true', default=False)
    args = parser.parse_args()
    initialize()
    asyncio.run(main(args.useapi))


if __name__ == "__main__":
    app_runner()
