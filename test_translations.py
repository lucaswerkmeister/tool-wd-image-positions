import pytest

import app as wdip


@pytest.mark.parametrize('depicted_message_key', wdip.depicted_properties.values())
def test_with_no_region_specified_unformatted(translations, language_code, depicted_message_key):
    """Test the image-*-without-region messages.

    The "$1 with no region specified:" messages are also used in JS,
    so they must be completely plain text,
    with no kind of formatting or parameter substitution.
    (We could actually contain let them HTML if we adjusted the JS code,
    but at the moment it’s not necessary.)
    """
    try:
        translation = translations[language_code][depicted_message_key]  # noqa: F405
    except KeyError:
        return

    assert '{' not in translation
    assert '<' not in translation
