from __future__ import annotations

import base64
import hashlib
import logging
import six
import secrets
from typing import Any, Dict, Optional
from operator import itemgetter

import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

import ckan.model as model
import ckan.plugins.toolkit as tk
import ckan.lib.munge as munge
from ckan.exceptions import CkanConfigurationException

CONFIG_DB_URL = "ckanext.drupal_idp.db_url"
CONFIG_SYNCHRONIZATION_ENABLED = "ckanext.drupal_idp.synchronization.enabled"

log = logging.getLogger(__name__)

DrupalId = int
UserDict = Dict[str, Any]


class Details:
    _props = ("name", "email", "id")

    def __init__(self, data):
        self.name, self.email, self.id = itemgetter(*self._props)(data)

    def __iter__(self):
        for prop in self._props:
            yield prop, getattr(self, prop)

    def make_userdict(self):
        return {
            "email": self.email,
            "name": munge.munge_name(self.name),
            "plugin_extras": {"drupal_idp": dict(self)},
        }


def is_synchronization_enabled() -> bool:
    return tk.asbool(tk.config.get(CONFIG_SYNCHRONIZATION_ENABLED))


def _make_password():
    return secrets.token_urlsafe(60)


def db_url() -> str:
    url = tk.config.get(CONFIG_DB_URL)
    if not url:
        raise CkanConfigurationException(
            f"drupal_idp plugin requires {CONFIG_DB_URL} config option."
        )
    return url


def session_cookie_name() -> str:
    """Compute name of the cookie that stores Drupal's SessionID.

    For D9 it's PREFIX + HASH, where:
      PREFIX: if isHTTPS then SSESS else SESS
      HASH: first 32 characters of sha256 hash of the site's hostname
            (does not include port)

    """
    server_name = tk.request.environ["HTTP_HOST"].split(":")[0]
    hash = hashlib.sha256(six.ensure_binary(server_name)).hexdigest()[:32]
    name = f"SESS{hash}"
    if tk.config["ckan.site_url"].startswith("https"):
        name = "S" + name
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
    - sha256 it
    - base64 it
    - replace pluses and slashes
    - strip out `=`-paddings

    """
    sha_hash = hashlib.sha256(six.ensure_binary(cookie_sid)).digest()
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
    """Fetch user data from Drupal's database.

    Method was written according to D9's table structure.

    """
    engine = sa.create_engine(db_url())
    try:
        user = engine.execute(
            """
        SELECT d.name name, d.mail email, d.uid id
        FROM sessions s
        JOIN users_field_data d
        ON s.uid = d.uid
        WHERE s.sid = %s
        """,
            [sid],
        ).first()
    except OperationalError:
        log.exception("Cannot get a user from Drupal's database")
        return
    # check if session has username,
    # otherwise is unauthenticated user session
    if user and user.name:
        return Details(user)


def _get_by_id(id: DrupalId) -> Optional[UserDict]:
    user = (
        model.Session.query(model.User.id)
        .filter(model.User.plugin_extras["drupal_idp"]["id"].astext == str(id))
        .one_or_none()
    )
    if user is None:
        return
    return tk.get_action("user_show")({"ignore_auth": True}, {"id": user.id})


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

    admin = tk.get_action("get_site_user")({"ignore_auth": True}, {})
    user = tk.get_action("user_create")({"user": admin["name"]}, user)
    return user


def _attach_details(id: str, details: Details) -> UserDict:
    """Update name, email and plugin_extras

    Raises:
    ValidationError if email or username is not unique
    """
    user = details.make_userdict()
    user["id"] = id

    admin = tk.get_action("get_site_user")({"ignore_auth": True}, {})
    user = tk.get_action("user_patch")({"user": admin["name"]}, user)
    return user


def get_or_create_from_details(details: Details) -> UserDict:
    """Get existing user or create new one.

    Raises:
    ValidationError if email or username is not unique
    """
    user = _get_by_id(details.id)
    if user:
        return user

    user = _get_by_email(details.email)
    if user:
        return _attach_details(user["id"], details)
    return _create_from_details(details)


def synchronize(user: UserDict, details: Details) -> UserDict:
    userobj = model.User.get(user["id"])
    if userobj.name != details.name:
        log.info(f"Synchronizing user {userobj.name} -> {details.name}")
        if model.User.get(details.name) is not None:
            raise tk.ValidationError(
                {"name": "This username is already taken"}
            )
        userobj.name = details.name
        model.Session.commit()
    if userobj.email != details.email:
        log.info(f"Synchronizing user {details.name}")
        user = _attach_details(user["id"], details)
    return user
