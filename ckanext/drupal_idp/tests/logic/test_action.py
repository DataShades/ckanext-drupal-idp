import pytest

import ckan.plugins.toolkit as tk
from ckan.tests.helpers import call_action

import ckanext.drupal_idp.utils as utils


class TestUserShow:
    def test_id_is_mandatory(self):
        with pytest.raises(tk.ValidationError):
            call_action('drupal_idp_user_show')

    def test_no_user_raises_an_error(self):
        with pytest.raises(tk.ObjectNotFound):
            call_action('drupal_idp_user_show', id=10)

    @pytest.mark.usefixtures("clean_db")
    def test_no_user_raises_an_error(self, details_data):
        details = utils.Details(**details_data)
        userdict = utils.get_or_create_from_details(details)

        user = call_action('drupal_idp_user_show', id=details.id)
        assert user["id"] == userdict["id"]
