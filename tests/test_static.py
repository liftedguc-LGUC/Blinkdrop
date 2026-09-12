import pytest


def test_root_serves_the_landing_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "How was your delivery" in response.text


def test_stylesheet_and_script_are_served(client):
    assert client.get("/styles.css").headers["content-type"].startswith("text/css")
    assert client.get("/app.js").status_code == 200


@pytest.mark.parametrize("path", ["/app/main.py", "/README.md", "/CLAUDE.md", "/requirements.txt"])
def test_non_public_files_are_not_served(client, path):
    assert client.get(path).status_code == 404
