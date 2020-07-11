import datetime
import time
from collections import defaultdict
from urllib.parse import quote

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


def parse_movie_roles(s: str):
    # Režie: Cédric Jimenez\nHrají: Jason Clarke, Rosamund Pike
    res = {}
    rec = s.split('\n')
    for r in rec:
        key, val, *_ = r.split(':') + ['', '']
        res[key.trim()] = [v.trim() for v in val.split(',')]
    return res


def parse_movie(pq):
    result = defaultdict(list)
    result['title'] += [pq('h3.subject > a.film').text()]
    movie_details = pq('p:first-of-type').text()
    genres, countries, year = parse_movie_details(movie_details)
    result['genre'] += genres
    result['country'] += countries
    result['year'] += [year]

    movie_roles = pq('p:last-of-type').text()
    roles = parse_movie_roles(movie_roles) or {}
    directors = [x.strip() for x in roles.get('Režie', '').split(',')]
    result['director'] += directors
    actors = [x.strip() for x in roles.get('Hrají', '').split(',')]
    result['actor'] += actors

    return result


csfd_throttle_stamp = datetime.datetime.utcfromtimestamp(0)


def search_movies(query):
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

    pq = PyQuery(content)
    results = [PyQuery(p) for p in pq('#search-films > div.content > ul.ui-image-list > li')]

    movies = []
    for movie_pq in results:
        result = parse_movie(movie_pq)

        jaro = jellyfish.jaro_winkler(result['title'], query)

        result = dict(match="{0}".format({round(jaro * 100)}), **result)

        movies += [result]

    return movies
