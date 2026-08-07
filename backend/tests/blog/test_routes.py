import pytest
from app import create_app


@pytest.fixture
def client():
    app = create_app('testing')
    app.config['TESTING'] = True
    return app.test_client()


def test_index_renders(client):
    r = client.get('/blog')
    assert r.status_code == 200
    assert b'<h1>The WhatsInDemand Blog</h1>' in r.data


def test_missing_post_404(client):
    assert client.get('/blog/does-not-exist').status_code == 404


def test_rss_content_type(client):
    r = client.get('/blog/rss.xml')
    assert r.status_code == 200
    assert 'xml' in r.content_type
