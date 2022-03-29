from __future__ import annotations
import dataclasses
import base64
import hashlib
import logging
import six
import secrets
from urllib.parse import unquote
from typing import Any, Dict, List, Optional, TypedDict
from typing_extensions import NotRequired

import ckan.model as model
import ckan.plugins.toolkit as tk
import ckan.lib.munge as munge
from . import signals

CONFIG_DB_URL = "ckanext.drupal_idp.db_url"
CONFIG_SYNCHRONIZATION_ENABLED = "ckanext.drupal_idp.synchronization.enabled"
CONFIG_STATIC_HOST = "ckanext.drupal_idp.host"
CONFIG_INHERIT_ADMIN_ROLE = "ckanext.drupal_idp.admin_role.inherit"
CONFIG_ADMIN_ROLE_NAME = "ckanext.drupal_idp.admin_role.name"
CONFIG_DRUPAL_VERSION = "ckanext.drupal_idp.drupal.version"
CONFIG_SAME_ID = "ckanext.drupal_idp.same_id"
CONFIG_EXTRA_FIELDS = "ckanext.drupal_idp.extra_fields"

DEFAULT_EXTRA_FIELDS = []
DEFAULT_ADMIN_ROLE = "administrator"
DEFAULT_DRUPAL_VERSION = "9"

log = logging.getLogger(__name__)

DrupalId = int
UserDict = Dict[str, Any]


class DetailsData(TypedDict):
    name: str
    email: str
    id: DrupalId
    roles: list[str]
    avatar: NotRequired[Optional[str]]
    fields: NotRequired[dict[str, list[Any]]]

@dataclasses.dataclass
class Details:
    name: str
    email: str
    id: DrupalId
    roles: List[str] = dataclasses.field(default_factory=list)
    avatar: Optional[str] = None
    fields: dict[str, list[Any]] = dataclasses.field(default_factory=dict)

    def is_sysadmin(self):
        return (
            tk.asbool(tk.config.get(CONFIG_INHERIT_ADMIN_ROLE))
            and tk.config.get(CONFIG_ADMIN_ROLE_NAME, DEFAULT_ADMIN_ROLE)
            in self.roles
        )

    def make_userdict(self):
        return {
            "email": self.email,
            "name": munge.munge_name(self.name),
            "sysadmin": self.is_sysadmin(),
            "plugin_extras": {"drupal_idp": dataclasses.asdict(self)},
        }


def is_synchronization_enabled() -> bool:
    return tk.asbool(tk.config.get(CONFIG_SYNCHRONIZATION_ENABLED))


def _make_password():
    return secrets.token_urlsafe(60)


def _get_host() -> str:
    host = tk.config.get(CONFIG_STATIC_HOST)
    if not host:
        host = tk.request.environ["HTTP_HOST"].split(":")[0]
    return host


def session_cookie_name() -> str:
    """Compute name of the cookie that stores Drupal's SessionID.

    For D9 it's PREFIX + HASH, where:
      PREFIX: if isHTTPS then SSESS else SESS
      HASH: first 32 characters of sha256 hash of the site's hostname
            (does not include port)

    """
    server_name = _get_host()
    hash = hashlib.sha256(six.ensure_binary(server_name)).hexdigest()[:32]
    name = f"SESS{hash}"
    if tk.config["ckan.site_url"].startswith("https"):
        name = "S" + name
    log.debug("Expected session-cookie name: %s", name)
    return name


def decode_sid(cookie_sid: str) -> str:
    """Decode Drupal's session cookie and turn it into SessionID.

    This method was written around Drupal v9.1.4 release. It's
    logic is unlikely to change for D9, but it may change in the
    future major releases, so keep an eye on it and check it first
    if you are sure that session cookie is there, but CKAN can't
    obtain user from Drupal's database.

    Algorythm:
    - get cookie value
    - url-unquote safe value(it's a cookie, some characters are encoded)
    - sha256 it
    - base64 it
    - replace pluses and slashes
    - strip out `=`-paddings

    """
    unquoted = unquote(cookie_sid)
    sha_hash = hashlib.sha256(six.ensure_binary(unquoted)).digest()
    base64_hash = base64.encodebytes(sha_hash)
    trans_rules = str.maketrans(
        {
            "+": "-",
            "/": "_",
            "=": "",
        }
    )
    sid = six.ensure_str(base64_hash.strip()).translate(trans_rules)
    return sid


def get_user_details(sid: str) -> Optional[Details]:
    """Fetch user data from Drupal's database."""
    import ckanext.drupal_idp.drupal as drupal

    adapter = drupal.get_adapter(
        tk.config.get(CONFIG_DRUPAL_VERSION, DEFAULT_DRUPAL_VERSION)
    )
    user = adapter.get_user_by_sid(sid)
    # check if session has username,
    # otherwise is unauthenticated user session

    if not user:
        return
    details_data = DetailsData(**user)
    roles = adapter.get_user_roles(user.id)
    details_data["avatar"] = adapter.get_avatar(user.id)
    details_data["roles"] = roles

    extra_fields = tk.aslist(tk.config.get(CONFIG_EXTRA_FIELDS, DEFAULT_EXTRA_FIELDS))
    details_data["fields"] = adapter.get_fields(user.id, extra_fields)

    return Details(**details_data)



def _get_by_email(email: str) -> Optional[UserDict]:
    user = (
        model.Session.query(model.User.id)
        .filter(model.User.email == email)
        .one_or_none()
    )
    if user is None:
        return
    return tk.get_action("user_show")({"ignore_auth": True}, {"id": user.id})


def _create_from_details(details: Details) -> UserDict:
    """Create a user with random password using Drupal's data.

    Raises:
    ValidationError if email or username is not unique
    """
    user = details.make_userdict()
    user["password"] = _make_password()
    if tk.asbool(tk.config.get(CONFIG_SAME_ID)):
        user["id"] = details.id

    admin = tk.get_action("get_site_user")({"ignore_auth": True}, {})
    user = tk.get_action("user_create")({"user": admin["name"]}, user)

    signals.after_create.send(user["id"], user=user)
    return user


def _attach_details(id: str, details: Details) -> UserDict:
    """Update name, email and plugin_extras

    Raises:
    ValidationError if email or username is not unique
    """
    admin = tk.get_action("get_site_user")({"ignore_auth": True}, {})
    user = tk.get_action("user_show")({"user": admin["name"]}, {"id": id, "include_plugin_extras": True})

    # do not drop extras that were set by other plugins
    extras = user.pop('plugin_extras', None) or {}
    patch = details.make_userdict()

    changed = False
    for k, v in patch.items():
        if k == 'plugin_extras':
            continue
        if v != user[k]:
            changed = True

    for k, v in patch['plugin_extras'].items():
        if k not in extras or extras[k] != v:
            changed = True

    if not changed:
        return tk.get_action("user_show")({"user": admin["name"]}, {"id": id})

    extras.update(patch['plugin_extras'])
    patch['plugin_extras'] = extras
    user.update(patch)

    # user_patch is not available in v2.9
    result = tk.get_action("user_update")({"user": admin["name"]}, user)
    signals.after_update.send(user["id"], user=user)

    return result


def get_or_create_from_details(details: Details) -> UserDict:
    """Get existing user or create new one.

    Raises:
    ValidationError if email or username is not unique
    """
    try:
        user = tk.get_action("drupal_idp_user_show")({"ignore_auth": True}, {"id": details.id})
    except tk.ObjectNotFound:
        user = _get_by_email(details.email)
        if user:
            user = synchronize(user, details)
    return user or _create_from_details(details)


def synchronize(user: UserDict, details: Details, force: bool = False) -> UserDict:
    userobj = model.User.get(user["id"])
    if userobj.name != details.name:
        log.info(f"Synchronizing user {userobj.name} -> {details.name}")
        if model.User.get(details.name) is not None:
            raise tk.ValidationError(
                {"name": "This username is already taken"}
            )
        userobj.name =  details.make_userdict()["name"]
        model.Session.commit()

    if (
        force or
        userobj.email != details.email
        or details.make_userdict()["plugin_extras"] != userobj.plugin_extras
    ):
        log.info(f"Synchronizing user {details.name}")
        user = _attach_details(user["id"], details)
    return user
