from __future__ import annotations

import base64
import dataclasses
import hashlib
import logging
import secrets
from typing import Any, Dict, List, Optional, TypedDict
from urllib.parse import unquote, urlparse

import six
from typing_extensions import NotRequired

import ckan.lib.munge as munge
import ckan.model as model
import ckan.plugins.toolkit as tk

from . import config, signals

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
        return config.inherit_admin_role() and config.admin_role_name() in self.roles

    def make_userdict(self):
        return {
            "email": self.email,
            "name": munge.munge_name(self.name),
            "sysadmin": self.is_sysadmin(),
            "plugin_extras": {"drupal_idp": dataclasses.asdict(self)},
        }


def is_synchronization_enabled() -> bool:
    return config.synchronization_enabled()


def _make_password():
    return secrets.token_urlsafe(60)


def _get_host() -> str:
    host = config.static_host()
    if not host:
        if tk.request:
            host = tk.request.environ["HTTP_HOST"].split(":")[0]
        else:
            host = urlparse(tk.config["ckan.site_url"]).hostname
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


def sid_into_uid(sid: str) -> DrupalId | None:
    """Fetch user data from Drupal's database."""
    import ckanext.drupal_idp.drupal as drupal

    adapter = drupal.get_adapter(config.drupal_version())
    return adapter.get_uid_by_sid(sid)


def get_user_details(uid: DrupalId) -> Optional[Details]:
    """Fetch user data from Drupal's database."""
    import ckanext.drupal_idp.drupal as drupal

    adapter = drupal.get_adapter(config.drupal_version())

    user = adapter.get_user_by_uid(uid)
    if not user:
        return
    details_data = DetailsData(**user)
    roles = adapter.get_user_roles(user.id)
    details_data["avatar"] = adapter.get_avatar(user.id)
    details_data["roles"] = roles

    extra_fields = config.extra_fields()
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
    if config.same_id():
        user["id"] = str(details.id)

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

    # in v2.10 you have to put sysadmin into context in order to get
    # plugin_extras. Mere `ignore_auth` doesn't work
    user = tk.get_action("user_show")(
        {"user": admin["name"], "keep_email": True},
        {"id": id, "include_plugin_extras": True},
    )

    # do not drop extras that were set by other plugins
    extras = user.pop("plugin_extras", None) or {}
    patch = details.make_userdict()

    changed = False
    for k, v in patch.items():
        if k == "plugin_extras":
            continue
        if v != user[k]:
            changed = True

    for k, v in patch["plugin_extras"].items():
        if k not in extras or extras[k] != v:
            changed = True

    if not changed:
        return tk.get_action("user_show")({"ignore_auth": True}, {"id": id})

    extras.update(patch["plugin_extras"])
    patch["plugin_extras"] = extras
    user.update(patch)

    # user_patch is not available in v2.9
    result = tk.get_action("user_update")({"ignore_auth": True}, user)
    signals.after_update.send(user["id"], user=user)

    return result


def get_or_create_from_details(details: Details) -> UserDict:
    """Get existing user or create new one.

    Raises:
    ValidationError if email or username is not unique
    """

    user: dict[str, Any] | None
    try:
        user = tk.get_action("drupal_idp_user_show")(
            {"ignore_auth": True}, {"id": details.id}
        )
    except tk.ObjectNotFound:
        user = _get_by_email(details.email)
        if user:
            user = synchronize(user, details)

    if user and user["state"] == "deleted":
        userobj = model.User.get(user["id"])
        if userobj:
            userobj.activate()
            model.Session.commit()
            user["state"] = userobj.state

    return user or _create_from_details(details)


def synchronize(user: UserDict, details: Details, force: bool = False) -> UserDict:
    userobj = model.User.get(user["id"])
    if userobj.name != details.name:
        log.info(f"Synchronizing user {userobj.name} -> {details.name}")
        if model.User.get(details.name) is not None:
            raise tk.ValidationError({"name": "This username is already taken"})
        userobj.name = details.make_userdict()["name"]
        model.Session.commit()

    current_extras = userobj.plugin_extras or {}

    if (
        force
        or userobj.email != details.email
        or details.make_userdict()["plugin_extras"]["drupal_idp"]
        != current_extras.get("drupal_idp")
    ):
        log.info(f"Synchronizing user {details.name}")
        user = _attach_details(user["id"], details)
    return user
