import logging

import ckan.plugins as plugins
import ckan.plugins.toolkit as tk


import ckanext.drupal_idp.utils as utils

log = logging.getLogger(__name__)


class DrupalIdpPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IAuthenticator, inherit=True)
    plugins.implements(plugins.IConfigurer)

    # IAuthenticator

    def identify(self):
        """This does drupal authorization.
        The drupal session contains the drupal id of the logged in user.
        We need to convert this to represent the ckan user."""
        cookie_sid = tk.request.cookies.get(utils.session_cookie_name())
        if not cookie_sid:
            return
        sid = utils.decode_sid(cookie_sid)
        details = utils.get_user_details(sid)
        if not details:
            return
        try:
            user = utils.get_or_create_from_details(details)
            if utils.is_synchronization_enabled():
                user = utils.synchronize(user, details)
        except tk.ValidationError as e:
            log.error(
                f"Cannot create user {details.name}<{details.email}>:"
                f" {e.error_summary}"
            )
            return
        tk.c.user = user["name"]

    # IConfigurer

    def update_config(self, config_):
        # If DB config is missing, the following line will raise
        # CkaneConfigurationException and won't allow server to start
        utils.db_url()
