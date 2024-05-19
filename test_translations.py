import pytest

from toolforge_i18n.translations_tests import *  # noqa: F401, F403

import app as wdip


@pytest.mark.parametrize('message_key', wdip.depicted_properties.values())
def test_with_no_region_specified_unformatted(language_code, message_key):
    """Test the image-*-without-region messages.

    The "$1 with no region specified:" messages are also used in JS,
    so they must be completely plain text,
    with no kind of formatting or parameter substitution.
    (We could actually contain let them HTML if we adjusted the JS code,
    but at the moment it’s not necessary.)
    """
    try:
        translation = translations[language_code][message_key]  # noqa: F405
    except KeyError:
        return

    assert '{' not in translation
    assert '<' not in translation
