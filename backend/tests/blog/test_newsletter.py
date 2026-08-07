from app.routes.blog import _valid_email


def test_valid_email():
    assert _valid_email('a@b.com')
    assert not _valid_email('nope')
    assert not _valid_email('')
    assert not _valid_email('a@b')
