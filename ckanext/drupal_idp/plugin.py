import logging

from ckan import model
import ckan.plugins as plugins
import ckan.plugins.toolkit as tk

from ckanext.drupal_idp.logic import action
from ckanext.drupal_idp.logic import auth
from ckanext.drupal_idp import helpers, utils, drupal, cli, views

CONFIG_SKIP_STATIC = "ckanext.drupal_idp.skip_static"
DEFAULT_SKIP_STATIC = False

log = logging.getLogger(__name__)


class DrupalIdpPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IAuthenticator, inherit=True)
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IClick)
    plugins.implements(plugins.IBlueprint)

    def get_blueprint(self):
        return views.get_blueprints()

    # IClick

    def get_commands(self):
        return cli.get_commands()

    # IActions

    def get_actions(self):
        return action.get_actions()

    # IAuthFunctions

    def get_auth_functions(self):
        return auth.get_auth_functions()

    # ITemplateHelpers

    def get_helpers(self):
        return helpers.get_helpers()

    # IAuthenticator

    def identify(self):
        """This does drupal authorization.
        The drupal session contains the drupal id of the logged in user.
        We need to convert this to represent the ckan user."""

        static = {
            ("static", "index"),
            ("webassets", "index"),
        }
        if (
            tk.asbool(tk.config.get(CONFIG_SKIP_STATIC, DEFAULT_SKIP_STATIC))
            and tk.get_endpoint() in static
        ):
            log.debug("Skip static route")
            return

        cookie_sid = tk.request.cookies.get(utils.session_cookie_name())
        if not cookie_sid:
            log.debug("No session cookie found")
            return
        sid = utils.decode_sid(cookie_sid)
        uid = utils.sid_into_uid(sid)
        if not uid:
            return

        try:
            user = tk.get_action("drupal_idp_user_initialize")(
                {"ignore_auth": True}, {"id": uid}
            )
            if utils.is_synchronization_enabled():
                user = tk.get_action("drupal_idp_user_synchronize")(
                    {"ignore_auth": True}, {"id": uid}
                )

        except tk.ObjectNotFound:
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

    def update_config(self, config_):
        # If DB config is missing, the following line will raise
        # CkaneConfigurationException and won't allow server to start
        drupal.db_url()
