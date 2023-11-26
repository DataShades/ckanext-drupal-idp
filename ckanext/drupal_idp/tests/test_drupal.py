import pytest

from ckan.exceptions import CkanConfigurationException

from ckanext.drupal_idp import config, drupal


class TestDbUrl:
    def test_default_value(self):
        assert drupal.db_url()

    @pytest.mark.ckan_config(config.CONFIG_DB_URL, "")
    def test_exception_with_missing_config(self):
        with pytest.raises(CkanConfigurationException):
            drupal.db_url()
