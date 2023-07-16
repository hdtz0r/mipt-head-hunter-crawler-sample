from aiohttp import ClientResponse, ClientResponseError, ClientSession, ServerTimeoutError
import aiohttp
from bs4 import BeautifulSoup
from multiprocessing import Lock
import asyncio
import re
from json import loads
from typing import Callable, Coroutine, Dict, List, Set, Tuple
from errors.parser_errors import DatasourceExternalError, NoSearchResults
from models.vacancy import Vacancy, Skill
from logging_utils import logger
from utils import async_retry, retry
from config.provider import configuration


class Pagination:

    _current_page: int = 0
    _last_page: int = 0
    _limit: int = 0
    _executor: Callable[[int, int], Coroutine[any, any, List[Vacancy]]]
    _lock: Lock

    def __init__(self, current_page: int, max_page: int, limit: int, executor: Callable[[int, int], Coroutine[any, any, List[Vacancy]]]) -> None:
        self._current_page = current_page
        self._last_page = max_page
        self._limit = limit
        self._executor = executor
        self._lock = Lock()

    def done(self) -> bool:
        self._lock.acquire()
        result = self._current_page >= self._last_page
        self._lock.release()
        return result

    def next(self):
        if self._executor:
            self._lock.acquire()
            try:
                result = self._executor(self._current_page, self._limit)
                self._current_page += 1
                return result
            finally:
                self._lock.release()

    def last(self, page_num: int):
        self._lock.acquire()
        self._last_page = page_num
        self._lock.release()


log = logger(__name__)


async def each_vacancy(search_query: str, limit: int, prefetch_size: int, use_api: bool = False):
    pagination = None
    vacancies_generator = None
    if use_api:
        pagination = Pagination(0, 1, prefetch_size, executor=lambda current_page,
                                prefetch_limit: _do_fetch_vacancies_using_api(search_query, prefetch_limit, current_page))
        vacancies_generator = _each_vacancy_using_api_pagination(
            pagination, limit)
    else:
        pagination = Pagination(0, 1, prefetch_size, executor=lambda current_page,
                                prefetch_limit: _do_fetch_vacancies(search_query, prefetch_limit, current_page))
        vacancies_generator = _each_vacancy_using_pagination(pagination, limit)

    async for vacancy in vacancies_generator:
        yield vacancy


async def _do_fetch_vacancies(search_query: str, limit: int = 50, page: int = 0):
    async with aiohttp.ClientSession() as session:
        return await _fetch_vacancies(session, search_query, limit, page)


@retry(errors=[TimeoutError, NoSearchResults, ClientResponseError])
async def _fetch_vacancies(session: ClientSession, search_query: str, limit: int = 50, page: int = 0) -> Tuple[Dict[str, any], Dict[str, any]]:
    request_parameters = {
        "no_magic": True,
        "l_save_area": False,
        "text": search_query,
        "excluded_text": None,
        "salary": None,
        "currency_code": "RUR",
        "experience": "doesNotMatter",
        "order_by": "relevance",
        "search_period": 0,
        "items_on_page": limit,
        "disableBrowserCache": True
    }
    if page:
        request_parameters["page"] = page

    url = f'{configuration.property("hh-search-endpoint")}?{"&".join( "=".join([k, "" if v is None else str(v)]) for k,v in request_parameters.items())}'

    response = await session.get(url, headers=_with_hh_headers(), timeout=configuration.property("request-timeout-in-seconds", 15))
    try:
        response.raise_for_status()
    except ClientResponseError as ex:
        if ex.code != 404:
            raise ex
        else:
            raise DatasourceExternalError(
                f'Could not fetch vacancies list since url is no longer valid {url}')

    payload = await _parse_vacancies_from_html(response)
    rs = payload.find_all("template", {
        "id": re.compile(r"HH.*InitialState")
    })
    if rs:
        for element in rs:
            for content in element.contents:
                try:
                    vacancies_payload = loads(content)
                    vacancies_search_result = vacancies_payload.get(
                        "vacancySearchResult", {})
                    pagination_definition = vacancies_search_result.get(
                        "paging", {})
                    return (vacancies_search_result.get("vacancies", {}), pagination_definition)
                except Exception as ex:
                    raise DatasourceExternalError(
                        "Could not parse vacancies json from template tag. Maybe response format is illegal or changed", ex)
    else:
        raise NoSearchResults(
            "Could not parse vacancies json from template tag cause it is missing. Maybe response format is illegal or changed")


async def _parse_vacancies_from_html(response: ClientResponse):
    return BeautifulSoup(await response.text(), 'html.parser')


async def _each_vacancy_using_pagination(pagination: Pagination, limit: int):
    total_generated = 0
    async with aiohttp.ClientSession() as session:
        while not pagination.done() and total_generated < limit:
            response = await pagination.next()

            vacancies_definitions, pagination_definition = response
            last_page = pagination_definition.get(
                "lastPage", {}).get("page", 1)
            pagination.last(last_page)

            coroutines = []
            # TODO seems like we should keep state via Cookie header to avoid such duplicate on next page

            visited_vacancies: Set[int] = set()
            pending_vacancies: Dict[str, Tuple[any]] = {}
            for vacancy_definition in vacancies_definitions[0:limit]:
                vacancy_id = vacancy_definition.get("vacancyId", None)
                type = vacancy_definition.get("type", "unknown")
                carrier_position = vacancy_definition.get("name", None)
                company_definition = vacancy_definition.get(
                    "company", {})
                company_name = company_definition.get("name", None)
                is_company_trusted = company_definition.get(
                    "@trusted", True)

                if vacancy_id and type == 'open' and is_company_trusted:
                    if not vacancy_id in visited_vacancies:
                        if total_generated < limit:
                            if company_name and carrier_position:
                                visited_vacancies.add(vacancy_id)
                                pending_vacancies[vacancy_id] = (
                                    carrier_position, company_name)
                                coroutines.append(
                                    _fetch_vacancy_details(session, vacancy_id))
                                total_generated += 1
                            else:
                                log.warn(
                                    "Vacancies search result have an invalid shape")
                        else:
                            break
                    else:
                        log.warn(
                            "Vacancy %s data is already gathered", vacancy_id)
                else:
                    log.warn("Vacancy %s from %s is ignored since it is in archive or company is untrusted",
                             carrier_position, company_name)

            vacancy_details_responses = await asyncio.gather(*coroutines)

            create_task_coroutines = []
            for id, vacancy_details_response in vacancy_details_responses:
                if id in pending_vacancies:
                    carrier_position, company_name = pending_vacancies.get(id)
                    create_task_coroutines.append(_create_vacancy_from_html(
                        id, carrier_position, company_name, vacancy_details_response))

            vacancies = await asyncio.gather(*create_task_coroutines)
            for vacancy in vacancies:
                yield vacancy


@async_retry(errors=[TimeoutError, ClientResponseError])
async def _fetch_vacancy_details(session: ClientSession, vacancy_id: int):
    url = f'{configuration.property("hh-vacancy-details-endpoint")}{vacancy_id}'
    response = await session.get(url, headers=_with_hh_headers(), timeout=configuration.property("request-timeout-in-seconds", 15))
    response.raise_for_status()
    return (vacancy_id, response)


@async_retry(errors=[TimeoutError, ClientResponseError])
async def _create_vacancy_from_html(id: int, carrier_position: str, company_name: str, response: ClientResponse) -> Vacancy:
    vacancy_details = BeautifulSoup(await response.text(), "html.parser")
    skill_elements = vacancy_details.find_all("span", attrs={
        "data-qa": "bloko-tag__text"
    })

    skills: List[Skill] = []

    if skill_elements:
        for skill_element in skill_elements:
            skills.append(Skill(name=str(skill_element.text).lower()))

    vacancy_description = ""
    description = vacancy_details.find_all("div", attrs={
        "data-qa": "vacancy-description"
    })

    if description:
        for description_part in description:
            text_lines = [v if isinstance(v, str) else str(
                v.text) for v in description_part.contents]
            vacancy_description = "\n".join(
                [vacancy_description]+[v.strip("\n").strip() for v in text_lines])

    vacancy: Vacancy = Vacancy(
        company=company_name,
        description=vacancy_description.strip("\n"),
        carrier_position=carrier_position,
        skills=skills,
        internal_id=id
    )
    log.info("Discovered vacancy %s", vacancy)
    return vacancy


def _with_hh_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.82",
        "Sec-Ch-Ua": '"Not.A/Brand";v="8", "Chromium";v="114", "Microsoft Edge";v="114"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": "Windows",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    }


async def _do_fetch_vacancies_using_api(search_query: str, limit: int = 50, page: int = 0):
    async with aiohttp.ClientSession() as session:
        return await _fetch_vacancies_using_api(session, search_query, limit, page)


@async_retry(errors=[TimeoutError, ClientResponseError])
async def _fetch_vacancies_using_api(session: ClientSession, search_query: str, limit: int = 50, page: int = 0):
    request_parameters = {
        "per_page": limit,
        "text": search_query
    }
    if page:
        request_parameters["page"] = page
    url = f'{configuration.property("hh-api-endpoint")}?{"&".join( "=".join([k, "" if v is None else str(v)]) for k,v in request_parameters.items())}'
    response = await session.get(url, headers=_with_hh_headers(), timeout=configuration.property("request-timeout-in-seconds", 15))
    response.raise_for_status()
    return await response.json()


@retry(errors=[TimeoutError, NoSearchResults])
async def _each_vacancy_using_api_pagination(pagination: Pagination, limit: int):
    total_generated = 0
    async with aiohttp.ClientSession() as session:
        while not pagination.done() and total_generated < limit:
            payload = await pagination.next()

            if not payload.get("found", 0):
                raise NoSearchResults("There is no vacancies")

            last_page = payload.get("pages", 1)
            pagination.last(last_page)

            coroutines = []
            for vacancy_definition in payload.get("items", [])[0:limit]:
                if total_generated < limit:
                    coroutines.append(_fetch_and_create_vacancy_using_api(
                        session, vacancy_definition))
                    total_generated += 1
                else:
                    break

            vacancies = await asyncio.gather(*coroutines)
            for vacancy in vacancies:
                if vacancy:
                    yield vacancy
                else:
                    total_generated -= 1


@async_retry(errors=[TimeoutError, ClientResponseError])
async def _fetch_and_create_vacancy_using_api(session: ClientSession, vacancy_definition: Dict[str, any]):
    vacancy_id = vacancy_definition.get("id", None)
    vacancy_url = vacancy_definition.get("url", None)
    carrier_position = vacancy_definition.get("name", None)
    company_name = vacancy_definition.get("employer", {}).get("name", None)
    is_company_trusted = vacancy_definition.get(
        "employer", {}).get("trusted", False)

    if vacancy_url and is_company_trusted:
        response = await session.get(vacancy_url, headers=_with_hh_headers(), timeout=configuration.property("request-timeout-in-seconds", 15))
        response.raise_for_status()
        payload = await response.json()

        if company_name and carrier_position:
            skills = [Skill(name=s.get("name").lower()) for s in filter(
                lambda s: True if s.get("name", False) else False, payload.get("key_skills", []))]
            vacancy: Vacancy = Vacancy(
                company=company_name,
                description=payload.get("description", "").strip("\n").strip(),
                carrier_position=carrier_position,
                skills=skills,
                internal_id=vacancy_id
            )
            log.info("Discovered vacancy %s", vacancy)
            return vacancy
    else:
        log.warn("Vacancy %s from %s is ignored since it is in archive or company is untrusted",
                 carrier_position, company_name)
