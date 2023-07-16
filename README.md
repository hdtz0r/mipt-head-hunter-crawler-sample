# Overview

Simple async crawler that support html or api call parse implementation
NOTE: that any vacancies from unstrusted companies or vacancies that is already in archive are ignored

# Basic requirements

Atleast Python 3.11.x

Requirements pyyaml, SQLAlchemy, beautifulsoup4 & aiohttp

```bash
pip install -r requiremenets.txt
```

# Configuration

The default one is generated automaticaly on startup if it does not exists

<details>

<summary>Default configuration</summary>

```yaml
log:
  file-name: sample-application.log
  file-path: ./
  level: 20 # log level
  max-part-size-in-bytes: 819200 # the size of log file
  max-size-in-bytes: 8388608 # the total size of logs
db-name: vacancies.db # The name of database 
vacancies-limit: 100 # total vacancies to fetch using relevance order
vacancies-prefetch: 50 # vacancies prefetch i.e. items per page
```

</details>

# Launching

activate venv and type 

```bash
cd ./src & python app.py
```

By default hh.ru crawler uses html parser but u can switch to api.hh.ru by using -api or --useapi argument

<details>

<summary>Below is the normal log output</summary>

```log
2023-07-16 21:28:32,012: [INFO] [MainProcess] [MainThread] [__main__]	-	Fetched total 100 vacancies
2023-07-16 21:28:32,520: [INFO] [MainProcess] [MainThread] [app_runner]	-	Method invokation app_runner tooks 10.98447895050049 seconds
```

</details>