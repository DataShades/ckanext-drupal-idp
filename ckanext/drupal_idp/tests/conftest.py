from ckanext.drupal_idp.utils import Details
import mock

import pytest

import ckanext.drupal_idp.utils as utils


@pytest.fixture
def details_data():
    return {"name": "test", "email": "test@example.net", "id": 123}


@pytest.fixture
def with_no_drupal_session(monkeypatch):
    monkeypatch.setattr(
        utils, "get_user_details", mock.Mock(return_value=None)
    )


@pytest.fixture
def with_drupal_session(monkeypatch, details_data):
    func = mock.Mock(return_value=Details(details_data))
    monkeypatch.setattr(utils, "get_user_details", func)
