import pytest

import ckan.model as model
import ckan.lib.munge as munge


import ckanext.drupal_idp.utils as utils


class TestDetails:
    def test_init(self, details_data):
        details = utils.Details(**details_data)
        for prop in details_data:
            assert getattr(details, prop) == details_data[prop]

    def test_into_user(self, details_data):
        details = utils.Details(**details_data)
        userdict = details.make_userdict()

        assert userdict == {
            "email": details_data["email"],
            "name": munge.munge_name(details_data["name"]),
            "sysadmin": False,
            "plugin_extras": {"drupal_idp": details_data},
        }

    def test_sysadmin_ignored_by_default(self, details_data):
        details_data["roles"].append(utils.DEFAULT_ADMIN_ROLE)
        assert not utils.Details(**details_data).is_sysadmin()

    @pytest.mark.ckan_config(utils.CONFIG_INHERIT_ADMIN_ROLE, "true")
    def test_sysadmin(self, details_data):
        assert not utils.Details(**details_data).is_sysadmin()
        details_data["roles"].append("not-an-admin")
        assert not utils.Details(**details_data).is_sysadmin()
        details_data["roles"].append(utils.DEFAULT_ADMIN_ROLE)
        assert utils.Details(**details_data).is_sysadmin()

    @pytest.mark.ckan_config(utils.CONFIG_INHERIT_ADMIN_ROLE, "true")
    @pytest.mark.ckan_config(utils.CONFIG_ADMIN_ROLE_NAME, "custom-admin")
    def test_sysadmin_with_custom_role(self, details_data):
        details_data["roles"].append(utils.DEFAULT_ADMIN_ROLE)
        assert not utils.Details(**details_data).is_sysadmin()
        details_data["roles"].append("custom-admin")
        assert utils.Details(**details_data).is_sysadmin()


class TestSynchronizationEnabled:
    def test_default_value(self):
        assert not utils.is_synchronization_enabled()

    @pytest.mark.ckan_config(utils.CONFIG_SYNCHRONIZATION_ENABLED, "true")
    def test_updated_value(self):
        assert utils.is_synchronization_enabled()


class TestSessionCookieName:
    @pytest.mark.usefixtures("with_request_context")
    def test_http(self):
        assert (
            utils.session_cookie_name()
            == "SESS49960de5880e8c687434170f6476605b"
        )

    @pytest.mark.usefixtures("with_request_context")
    def test_https(self, ckan_config, monkeypatch):
        monkeypatch.setitem(ckan_config, "ckan.site_url", "https://test.net")
        assert (
            utils.session_cookie_name()
            == "SSESS49960de5880e8c687434170f6476605b"
        )

    @pytest.mark.ckan_config(utils.CONFIG_STATIC_HOST, "my.site.com")
    def test_static_host(self):
        assert (
            utils.session_cookie_name()
            == "SESSe181b034216cdf301d365b2fc8aa54db"
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
        details = utils.Details(**details_data)
        utils.get_or_create_from_details(details)
        user = model.User.get(details_data["name"])
        assert user.name == details_data["name"]
        assert user.plugin_extras["drupal_idp"] == details_data


@pytest.mark.usefixtures("clean_db")
class TestGetOrCreation:

    def test_default_native_id(self, details_data):
        details = utils.Details(**details_data)
        userdict = utils.get_or_create_from_details(details)
        assert userdict["id"] != details_data["id"]

    @pytest.mark.ckan_config(utils.CONFIG_SAME_ID, "true")
    def test_same_id(self, details_data):
        details = utils.Details(**details_data)
        userdict = utils.get_or_create_from_details(details)
        assert userdict["id"] == str(details_data["id"])

    def test_user_sync(self, details_data, monkeypatch, ckan_config):
        details = utils.Details(**details_data)
        userdict = utils.get_or_create_from_details(details)
        user = model.User.get(userdict["id"])
        user.email = "hello@world"
        user.name = "hello"
        model.Session.commit()

        userdict = utils.get_or_create_from_details(details)
        assert userdict["name"] != details_data["name"]
        assert userdict["name"] == "hello"
        user = model.User.get(userdict["id"])
        assert user.email != details_data["email"]
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

    def test_plugin_extras_not_erased(self, details_data):
        details = utils.Details(**details_data)
        userdict = utils.get_or_create_from_details(details)
        user = model.User.get(userdict["id"])
        user.plugin_extras = {
            "test": {"key": "value"}
        }
        utils.synchronize(userdict, details, force=True)
        user = model.User.get(userdict["id"])
        assert "drupal_idp" in user.plugin_extras
        assert "test" in user.plugin_extras
