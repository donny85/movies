import copy
import datetime
import time
from collections import defaultdict
from datetime import date
from urllib.parse import quote

import jellyfish
import requests
from pyquery import PyQuery

from lib.settings import CRAWLER_USER_AGENT, CSFD_MAX_REQUESTS_PER_MINUTE
from lib.utils import str_pct, tokenize_string

AVAILABLE_COLUMNS = ('title', 'genre1', 'genre2', 'director', 'director2',
                     'country', 'country2', 'year', 'actor', 'actor2',
                     'jaro', 'match', 'filename',)

FIRST_MOVIE_YEAR = 1878
MIN_YEAR = FIRST_MOVIE_YEAR
MAX_YEAR = date.today().year

csfd_throttle_stamp = None


def request_csfd_movies(query: str):
    global csfd_throttle_stamp

    search_url = '{0}?q={1}'.format("https://www.csfd.cz/hledat/", quote(query))

    if csfd_throttle_stamp is not None:
        delta = (csfd_throttle_stamp - datetime.datetime.now()).total_seconds()
        if delta > 0:
            time.sleep(delta)

    csfd_throttle_stamp = datetime.datetime.now() + datetime.timedelta(seconds=(CSFD_MAX_REQUESTS_PER_MINUTE / 60))

    res = requests.get(search_url, headers={'User-Agent': CRAWLER_USER_AGENT})
    content = res.content  # release connection back to pool
    res.raise_for_status()

    if not content:
        return []

    pq = PyQuery(content)
    return [PyQuery(p) for p in pq('#search-films > div.content > ul.ui-image-list > li')]


def parse_csfd_movie(pq) -> dict:
    def parse_movie_details(details: str):
        # Akční / Životopisný, Francie / Velká Británie, 2017
        details = details.split(',')
        part_genres = details[0] if len(details) else ''
        part_countries = details[1].strip() if len(details) > 1 else ''

        years_, countries_ = ([str(part_countries)], []) if part_countries.isnumeric() \
            else ([details[2].strip()] if len(details) > 2 else [], part_countries)

        [genres_, countries_] = map(lambda s: [t.strip() for t in s.split('/')], (part_genres, countries_))

        return genres_, countries_, years_

    def parse_movie_roles(line: str):
        # Režie: Cédric Jimenez\nHrají: Jason Clarke, Rosamund Pike
        roles_ = defaultdict(list)
        for r in line.split('\n'):
            key, val, *_ = r.split(':') + ['', '']
            roles_[key.strip()] = [v.strip() for v in val.split(',')]
        return roles_

    movie = defaultdict(list)
    movie['title'] += [pq('h3.subject > a.film').text()]
    movie_details = pq('p:first-of-type').text()
    genres, countries, years = parse_movie_details(movie_details)
    movie['genre'] += genres
    movie['country'] += countries
    movie['year'] += years

    movie_roles = pq('p:last-of-type').text()
    roles = parse_movie_roles(movie_roles)
    movie['director'] += roles['Režie']
    movie['actor'] += roles['Hrají']

    return movie


def search_movies(query: str) -> list:
    csfd_movies, movies = request_csfd_movies(query), []

    for csfd_movie in csfd_movies:
        movie = parse_csfd_movie(csfd_movie)
        match = movie_query_match(query, movie)
        movies += [dict(match=match, **movie)]

    return movies


def movie_file_name(movie: dict):
    [title] = movie.get('title', ('BEZ NÁZVU',))
    director = ', '.join(filter(None, movie.get('director', ())))
    [year] = movie.get('year', ('0000',))
    genres = ', '.join(filter(None, movie.get('genre', ())))
    actors = ', '.join(filter(None, movie.get('actor', ())))
    desc = '; '.join(filter(None, [director, genres, actors]))
    details = ', '.join(filter(None, [year, desc]))
    fn = '{0} ({1})'.format(title, details) if details else title

    # Supersmradi - Malí Géniové 2 (1997, Bob Clark; Rodinný, Komedie; Jon Voight, Scott Baio)
    return fn.replace(r'/', '_')


def parse_csv_movie(columns, line):
    movie = defaultdict(list)

    for i, col in enumerate(columns):
        if line[i]:
            movie[col] += [line[i]]

    # dict(title=["Supersmradi - Malí Géniové 2"], actor=["Jon Voight", "Scott Baio"], director=["Bob Clark"], ...=[])
    return movie


def movie_query_match(query: str, movie: dict) -> list:
    match = []

    movie_string = ' '.join([' '.join(v) for k, v in movie.items() if k not in ('match',)])
    query_tokens = set(tokenize_string(query))
    movie_tokens = set(tokenize_string(movie_string))

    # remove small numbers from the comparison
    for x in map(str, range(10)):
        query_tokens.discard(x), movie_tokens.discard(x)

    # compare query and result and try to find perfect match
    matching_vals = movie_tokens.intersection(query_tokens)
    matching_years = (y for y in matching_vals if (y.isdigit() and MIN_YEAR <= int(y) < MAX_YEAR))
    [movie_year] = movie.get('year')

    comp_query_tokens = copy.deepcopy(query_tokens)
    comp_query_tokens.discard(movie_year)

    [title] = movie['title']
    comp_query_string = ' '.join(sorted(comp_query_tokens))
    comp_title_string = ' '.join(set(sorted(tokenize_string(title))))
    jaro = jellyfish.jaro_winkler(comp_query_string, comp_title_string)
    match += [str_pct(min(jaro, 0.99))]

    if movie_year in matching_years and query_tokens.issubset(movie_tokens):
        match += ['100']

    return match
