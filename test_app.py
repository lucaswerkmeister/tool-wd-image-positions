import flask
import pytest

import app as wdip


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


@pytest.mark.parametrize('input', [
    'Vegetarian_Pizza.jpg',
    'Vegetarian Pizza.jpg',
    'File:Vegetarian Pizza.jpg',
    'File:Vegetarian_Pizza.jpg',
    'https://commons.wikimedia.org/wiki/File:Vegetarian_Pizza.jpg',
    'https://commons.wikimedia.org/wiki/File:Vegetarian_Pizza.jpg#Summary',
    'https://commons.wikimedia.org/wiki/Special:FilePath/Vegetarian_Pizza.jpg',
    'https://commons.wikimedia.org/w/index.php?title=File:Vegetarian_Pizza.jpg&action=history',
])
def test_parse_image_title_input(input):
    expected = 'Vegetarian_Pizza.jpg'
    actual = wdip.parse_image_title_input(input)
    assert expected == actual
