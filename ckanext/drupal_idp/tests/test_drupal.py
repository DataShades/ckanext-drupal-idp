import pytest

from ckan.exceptions import CkanConfigurationException

import ckanext.drupal_idp.utils as utils
import ckanext.drupal_idp.drupal as drupal

class TestDbUrl:
    def test_default_value(self):
        assert drupal.db_url()

    @pytest.mark.ckan_config(utils.CONFIG_DB_URL, "")
    def test_exception_with_missing_config(self):
        with pytest.raises(CkanConfigurationException):
            drupal.db_url()
