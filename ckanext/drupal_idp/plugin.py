from __future__ import annotations

import logging
from typing import Any

from ckan import model
import ckan.plugins as plugins
import ckan.plugins.toolkit as tk
from ckan.views import _get_user_for_apitoken

from ckanext.drupal_idp.logic import action
from ckanext.drupal_idp.logic import auth
from ckanext.drupal_idp import helpers, utils, drupal, cli, views, config

log = logging.getLogger(__name__)


@tk.blanket.actions(action.get_actions)
@tk.blanket.auth_functions(auth.get_auth_functions)
@tk.blanket.helpers(helpers.get_helpers)
@tk.blanket.blueprints(views.get_blueprints)
@tk.blanket.cli(cli.get_commands)
@tk.blanket.config_declarations
class DrupalIdpPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IAuthenticator, inherit=True)
    plugins.implements(plugins.IConfigurer)

    # IAuthenticator

    def identify(self):
        """This does drupal authorization.

        The drupal session contains the drupal id of the logged in user.
        We need to convert this to represent the ckan user.
        """

        # skip routes with static content as they never require authentication
        static = {
            ("static", "index"),
            ("webassets", "index"),
        }
        if config.skip_static() and tk.get_endpoint() in static:
            log.debug("Skip static route")
            return

        # skip authentication for user set via API token. Most likely this is
        # XLoader request and we don't want it to authenticate via drupal
        api_user = _get_user_for_apitoken()
        if api_user:
            return

        # this option controls whether the current user is logged out
        # automatically if drupal has no active session for him
        kick_missing = tk.check_ckan_version("2.10") and config.kick_missing_session()

        # get the value of drupal's session cookie. The name of the cookie is
        # based on the application hostname
        cookie_sid = tk.request.cookies.get(utils.session_cookie_name())
        if not cookie_sid:
            log.debug("No session cookie found")
            if kick_missing:
                tk.logout_user()
            return

        # if session cookkie detected, pull user's UID from drupal's database
        sid = utils.decode_sid(cookie_sid)
        uid = utils.sid_into_uid(sid)
        if not uid:
            if kick_missing:
                tk.logout_user()
            return

        # If UID exists, create or update user's details on CKAN side
        try:
            user = tk.get_action("drupal_idp_user_initialize")(
                {"ignore_auth": True}, {"id": uid}
            )
            if utils.is_synchronization_enabled():
                user = tk.get_action("drupal_idp_user_synchronize")(
                    {"ignore_auth": True}, {"id": uid}
                )

        except tk.ObjectNotFound:
            # that can happen when drupal's database in a mess and session
            # table contains identifiers on non-existing users. That's a data
            # integrity error, and it may have sense to logout user from CKAN
            # in such situation. But this can happen only when everything is
            # broken, so doing nothing is also an appropriate strategy
            log.warning("No drupal user found for UID %s", uid)
            return

        except tk.ValidationError as e:
            log.error("Cannot create or synchronize user: %s", e.error_summary)
            return

        if tk.check_ckan_version("2.10"):
            tk.login_user(model.User.get(user["name"]))
        else:
            tk.c.user = user["name"]

    # IConfigurer

    def update_config(self, config_: Any):
        # If DB config is missing, the following line will raise
        # CkaneConfigurationException and won't allow server to start
        drupal.db_url()
