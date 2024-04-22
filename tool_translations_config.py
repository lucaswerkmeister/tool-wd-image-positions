from toolforge_i18n.translations import TranslationsConfig


def _identity(s: str) -> str:
    return s


_variables = {
    'index-paragraph-1': ['P2677', 'P180', 'P9664'],
    'index-paragraph-2': ['url_wikidata', 'P18', 'url_sdoc'],
    'index-placeholder-item-id': ['example_id', 'example_url'],  # example_url is *not* a “url” argument
    'index-placeholder-file-title': ['example_name', 'example_id', 'example_url'],  # ditto
}


_derived_messages = {
    'index-h1': ('tool-name', _identity),
    'html-title': ('tool-name', _identity),
    'nav-tool-name': ('tool-name', _identity),
}


_allowed_html_elements = {
    'abbr': {'title'},
    'small': set(),
}


config = TranslationsConfig(
    variables=_variables,
    derived_messages=_derived_messages,
    allowed_html_elements=_allowed_html_elements,
)
