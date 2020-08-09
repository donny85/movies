COLUMNS = {  # names of the group-by subdirectories
    'title': "Podle abecedy",
    'year': "Podle roku",
    'genre': "Podle žánru",
    'country': "Podle země",
    'director': "Podle režie",
    'actor': "Podle obsazení",
}

DEFAULT_COLUMNS = (
    'filename', 'title', 'year', 'genre', 'genre', 'country', 'country', 'director', 'actor', 'actor', 'match',
)

DEFAULT_SKIPPING_COLUMNS = ('director', 'title', 'year',)

CRAWLER_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.129 " \
                     "Safari/537.36"

CSFD_MAX_REQUESTS_PER_MINUTE = 60

FLAT_GROUPBY_COLUMNS = ('title', 'filename',)  # these group-by directories doesn't group into subdirectories by value

DEFAULT_GROUPBY_COLUMNS = ('title', 'genre', 'country', 'director', 'actor',)
