import datetime
import time
from urllib.parse import quote
import yaml

import jellyfish
import requests
from pyquery import PyQuery

from lib.settings import CRAWLER_USER_AGENT, CSFD_THROTTLE_PER_MINUTE

SEARCH_URL = "https://www.csfd.cz/hledat/"

AVAILABLE_COLUMNS = ('title', 'genre1', 'genre2', 'director', 'director2',
                     'country', 'country2', 'year', 'actor', 'actor2',
                     'jaro', 'match', 'filename',)


def parse_movie_details(details: str):
    # Akční / Životopisný, Francie / Velká Británie, 2017
    details = details.split(',')
    genres = details[0] if len(details) else ''
    countries = details[1].strip() if len(details) > 1 else ''
    if countries.isnumeric():
        year = '{0}'.format(countries)
        countries = ''
    else:
        year = details[2] if len(details) > 2 else ''
    [genres, countries] = map(lambda s: [t.strip() for t in s.split('/')], (genres, countries))
    return genres, countries, year.strip()


def parse_movie(pq, filter_columns=None, add_cols=None):
    result = add_cols or {}

    result['title'] = pq('h3.subject > a.film').text()

    movie_details = pq('p:first-of-type').text()
    """Akční / Životopisný, Francie / Velká Británie, 2017"""

    if not filter_columns or filter_columns.intersection({'genre', 'genre2', 'country', 'country2', 'year'}):
        genres, countries, year = parse_movie_details(movie_details)
        result['genre'], result['genre2'], *_ = genres + ['', '']
        result['country'], result['country2'], *_ = countries + ['', '']
        result['year'] = year

    movie_roles = pq('p:last-of-type').text()
    """Režie: Cédric Jimenez\nHrají: Jason Clarke, Rosamund Pike"""

    if not filter_columns or filter_columns.intersection({'director', 'director2', 'actor', 'actor2'}):
        roles = yaml.safe_load(movie_roles) or {}
        directors = [x.strip() for x in roles.get('Režie', '').split(',')]
        result['director'], result['director2'], *_ = directors + ['', '']
        actors = [x.strip() for x in roles.get('Hrají', '').split(',')]
        result['actor'], result['actor2'], *_ = actors + ['', '']

    return result


csfd_throttle_stamp = datetime.datetime.utcfromtimestamp(0)


def search_movies(query, filter_columns=None, add_cols=None):
    global csfd_throttle_stamp

    search_url = '{url}?q={query}'.format(url=SEARCH_URL, query=quote(query))

    if csfd_throttle_stamp is not None:
        delta = (csfd_throttle_stamp - datetime.datetime.now()).total_seconds()
        if delta > 0:
            time.sleep(delta)

    csfd_throttle_stamp = datetime.datetime.now() + datetime.timedelta(seconds=(CSFD_THROTTLE_PER_MINUTE / 60))

    res = requests.get(search_url, headers={'User-Agent': CRAWLER_USER_AGENT})
    content = res.content  # release connection back to pool
    res.raise_for_status()

    if not content:
        return []

    if filter_columns is not None:
        filter_columns = set(filter_columns)

    pq = PyQuery(content)
    results = [PyQuery(p) for p in pq('#search-films > div.content > ul.ui-image-list > li')]

    movies = []
    for movie_pq in results:
        result = parse_movie(movie_pq, filter_columns, add_cols)

        jaro = jellyfish.jaro_winkler(result['title'], query)

        if filter_columns is None or 'match' in filter_columns:
            result = dict(match="{0}".format({round(jaro * 100)}), **result)

        movies += [result]

    return movies
