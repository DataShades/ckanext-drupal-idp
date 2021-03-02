import pytest

import ckan.model as model
import ckan.lib.munge as munge
from ckan.exceptions import CkanConfigurationException

import ckanext.drupal_idp.utils as utils


class TestDetails:
    def test_init(self, details_data):
        details = utils.Details(details_data)
        for prop in details_data:
            assert getattr(details, prop) == details_data[prop]

    def test_into_dict(self, details_data):
        details = utils.Details(details_data)
        assert dict(details) == details_data

    def test_into_user(self, details_data):
        details = utils.Details(details_data)
        userdict = details.make_userdict()

        assert userdict == {
            "email": details_data["email"],
            "name": munge.munge_name(details_data["name"]),
            "plugin_extras": {"drupal_idp": details_data},
        }


class TestSynchronizationEnabled:
    def test_default_value(self):
        assert not utils.is_synchronization_enabled()

    @pytest.mark.ckan_config(utils.CONFIG_SYNCHRONIZATION_ENABLED, "true")
    @pytest.mark.usefixtures("ckan_config")
    def test_updated_value(self):
        assert utils.is_synchronization_enabled()


class TestDbUrl:
    def test_default_value(self):
        assert utils.db_url()

    @pytest.mark.ckan_config(utils.CONFIG_DB_URL, "")
    @pytest.mark.usefixtures("ckan_config")
    def test_exception_with_missing_config(self):
        with pytest.raises(CkanConfigurationException):
            utils.db_url()


class TestSessionCookieName:
    @pytest.mark.usefixtures("with_request_context")
    def test_http(self):
        assert (
            utils.session_cookie_name()
            == "SESSeb97964bfaedb6fad496cc0746f6ab7b"
        )

    @pytest.mark.usefixtures("with_request_context")
    def test_https(self, ckan_config, monkeypatch):
        monkeypatch.setitem(ckan_config, "ckan.site_url", "https://test.net")
        assert (
            utils.session_cookie_name()
            == "SSESSeb97964bfaedb6fad496cc0746f6ab7b"
        )


def test_decode_sid():
    cookie = "x7kHcLGoGrro66NTty7EPBluIVK8HNUOMvVpUT_6g7o"
    expected = "y7ZGy1KGrckATBB5gixhyKBS2BfhMeLmdMuX4_H-Uak"
    assert utils.decode_sid(cookie) == expected


class TestFixtures:
    def test_no_session(self, with_no_drupal_session):
        assert utils.get_user_details("sid") is None

    def test_with_session(self, with_drupal_session):
        assert utils.get_user_details("sid") is not None


@pytest.mark.usefixtures("clean_db")
class TestGetOrCreation:
    def test_user_created(self, details_data):
        assert model.User.get(details_data["name"]) is None
        details = utils.Details(details_data)
        utils.get_or_create_from_details(details)
        user = model.User.get(details_data["name"])
        assert user.name == details_data["name"]
        assert user.plugin_extras["drupal_idp"] == details_data


@pytest.mark.usefixtures("clean_db")
class TestGetOrCreation:
    def test_user_sync(self, details_data, monkeypatch, ckan_config):
        details = utils.Details(details_data)
        userdict = utils.get_or_create_from_details(details)
        user = model.User.get(userdict["id"])
        user.email = "hello@world"
        user.name = "hello"
        model.Session.commit()

        userdict = utils.get_or_create_from_details(details)
        assert userdict["name"] == "hello"
        user = model.User.get(userdict["id"])
        assert user.email == "hello@world"

        utils.synchronize(userdict, details)
        userdict = utils.get_or_create_from_details(details)
        assert userdict["name"] == details_data["name"]
        user = model.User.get(userdict["id"])
        assert user.email == details_data["email"]

        assert (
            model.Session.query(model.User).filter_by(name="hello").count()
            == 0
        )
        assert (
            model.Session.query(model.User)
            .filter_by(name=details_data["name"])
            .count()
            == 1
        )
