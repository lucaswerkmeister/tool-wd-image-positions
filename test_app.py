import flask
import pytest

import app as wdip


@pytest.mark.parametrize('image_title, expected', [
    ('Foo Bar', 'Foo_Bar'),
    ('File:Foo_Bar', 'Foo_Bar'),
    ('File:Foo Bar', 'Foo_Bar'),
])
def test_file_redirect(image_title, expected):
    with wdip.app.test_request_context():
        response = flask.make_response(wdip.file(image_title))
    assert str(response.status_code).startswith('3')
    location = response.headers['Location']
    assert location.startswith('/file/')
    actual = location[len('/file/'):]
    assert expected == actual


@pytest.mark.parametrize('input, expected', [
    ('Q1231009', 'Q1231009'),
    ('http://www.wikidata.org/entity/Q1231009', 'Q1231009'),
    ('https://www.wikidata.org/wiki/Special:EntityData/Q1231009', 'Q1231009'),
    ('https://www.wikidata.org/wiki/Q1231009', 'Q1231009'),
    ('https://www.wikidata.org/wiki/Q1231009#P18', 'Q1231009'),
    ('https://www.wikidata.org/w/index.php?title=Q1231009&action=history', 'Q1231009'),
    ('P31', 'P31'),
    ('L1', 'L1'),
    ('L1-S1', 'L1-S1'),
    ('L1-F1', 'L1-F1'),
])
def test_parse_item_id_input(input, expected):
    actual = wdip.parse_item_id_input(input)
    assert expected == actual
