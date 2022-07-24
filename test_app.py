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
    'M106092414',
    'https://commons.wikimedia.org/entity/M106092414',
    'https://commons.wikimedia.org/wiki/Special:EntityData/M106092414',
])
def test_parse_image_title_input(input):
    expected = 'Vegetarian_Pizza.jpg'
    actual = wdip.parse_image_title_input(input)
    assert expected == actual


@pytest.mark.parametrize('input', [
    'CSD Berlin 2022 - Lucas Werkmeister - 49 - Do You Think You’re More Tired Of The War Than We Are?.jpg',
    'File:CSD Berlin 2022 - Lucas Werkmeister - 49 - Do You Think You’re More Tired Of The War Than We Are?.jpg',
    'https://commons.wikimedia.org/wiki/File:CSD_Berlin_2022_-_Lucas_Werkmeister_-_49_-_Do_You_Think_You%E2%80%99re_More_Tired_Of_The_War_Than_We_Are%3F.jpg',
    'https://commons.wikimedia.org/wiki/File:CSD_Berlin_2022_-_Lucas_Werkmeister_-_49_-_Do_You_Think_You%E2%80%99re_More_Tired_Of_The_War_Than_We_Are%3F.jpg#Summary',
    'https://commons.wikimedia.org/w/index.php?title=File:CSD_Berlin_2022_-_Lucas_Werkmeister_-_49_-_Do_You_Think_You%E2%80%99re_More_Tired_Of_The_War_Than_We_Are%3F.jpg&action=history',
])
def test_parse_image_title_input_question_mark(input):
    expected = 'CSD_Berlin_2022_-_Lucas_Werkmeister_-_49_-_Do_You_Think_You’re_More_Tired_Of_The_War_Than_We_Are?.jpg'
    actual = wdip.parse_image_title_input(input)
    assert expected == actual
