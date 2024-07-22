from toolforge_i18n.translations import TranslationsConfig, language_code_to_babel


def _identity(s: str) -> str:
    return s


_variables = {
    'nav-logged-in': ['user_link', 'user_name'],
    'index-paragraph-1': ['P2677', 'P180', 'P9664'],
    'index-paragraph-2': ['url_wikidata', 'P18', 'url_sdoc'],
    'index-placeholder-item-id': ['example_id', 'example_url'],  # example_url is *not* a “url” argument
    'index-placeholder-file-title': ['example_name', 'example_id', 'example_url'],  # ditto
    'alert-not-logged-in': ['url'],
    'file-not-found-body': ['title'],
    'wrong-data-value-type-paragraph-1': ['expected_data_value_type', 'actual_data_value_type'],
}


_derived_messages = {
    'index-h1': ('tool-name', _identity),
    'html-title': ('tool-name', _identity),
    'nav-tool-name': ('tool-name', _identity),
    'settings-link': ('settings', _identity),
    'settings-h1': ('settings', _identity),
}


_allowed_html_elements = {
    'abbr': {'title'},
    'code': set(),
    'noscript': set(),
    'q': set(),
    'small': set(),
}


def _language_code_to_babel(code: str) -> str:
    mapped = language_code_to_babel(code)
    if mapped != code:
        return mapped
    return {
        # kaa (Karakalpak) is in Latin script in MediaWiki,
        # but its closest relatives in Babel are all in Cyrillic script;
        # uz (Uzbek) has the same plural forms,
        # and its list formatting (“X and Y”) is probably intelligible to Karakalpak speakers for geopolitical reasons
        'kaa': 'uz',
    }.get(code, code.partition('-')[0])


config = TranslationsConfig(
    variables=_variables,
    derived_messages=_derived_messages,
    language_code_to_babel=_language_code_to_babel,
    allowed_html_elements=_allowed_html_elements,
    check_translations=False,
)
