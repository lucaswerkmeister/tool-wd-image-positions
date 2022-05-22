import cachetools
import mwapi
import threading


_messages_cache = cachetools.TTLCache(maxsize=1024, ttl=24*60*60)
_messages_cache_lock = threading.RLock()


@cachetools.cached(cache=_messages_cache,
                   lock=_messages_cache_lock)
def _load_messages(language):
    session = mwapi.Session('https://www.wikidata.org')
    response = session.get(action='query',
                           meta='allmessages',
                           ammessages=['wikibase-snakview-variations-somevalue-label',
                                       'wikibase-snakview-variations-novalue-label'],
                           amlang=language,
                           formatversion=2)
    messages = {}
    for message in response['query']['allmessages']:
        messages[message['name']] = {
            'language': language,  # the API doesn’t tell us which language it actually used :(
            'value': message['content'],
        }
    return messages


def somevalue(language):
    return _load_messages(language)['wikibase-snakview-variations-somevalue-label']


def novalue(language):
    return _load_messages(language)['wikibase-snakview-variations-novalue-label']
