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
