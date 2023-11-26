from __future__ import annotations

import ckan.plugins.toolkit as tk

CONFIG_ADMIN_ROLE_NAME = "ckanext.drupal_idp.admin_role.name"
CONFIG_DB_URL = "ckanext.drupal_idp.db_url"
CONFIG_DRUPAL_VERSION = "ckanext.drupal_idp.drupal.version"
CONFIG_EXTRA_FIELDS = "ckanext.drupal_idp.extra_fields"
CONFIG_FOCE_SYNC = "ckanext.drupal_idp.synchronization.force"

CONFIG_INHERIT_ADMIN_ROLE = "ckanext.drupal_idp.admin_role.inherit"
CONFIG_KICK_MISSING_SESSION = "ckanext.drupal_idp.kick_missing_session"
CONFIG_PUBLIC_PATH = "ckanext.drupal_idp.public_path"
CONFIG_SAME_ID = "ckanext.drupal_idp.same_id"
CONFIG_SKIP_STATIC = "ckanext.drupal_idp.skip_static"

CONFIG_STATIC_HOST = "ckanext.drupal_idp.host"
CONFIG_SYNCHRONIZATION_ENABLED = "ckanext.drupal_idp.synchronization.enabled"

DEFAULT_ADMIN_ROLE = "administrator"
DEFAULT_DRUPAL_VERSION = "9"
DEFAULT_EXTRA_FIELDS = []
DEFAULT_FORCE_SYNC = False
DEFAULT_KICK_MISSING_SESSION = False
DEFAULT_PUBLIC_PATH = "/sites/default/files/"
DEFAULT_SKIP_STATIC = False


def kick_missing_session() -> bool:
    return tk.asbool(
        tk.config.get(CONFIG_KICK_MISSING_SESSION, DEFAULT_KICK_MISSING_SESSION)
    )


def skip_static() -> bool:
    return tk.asbool(tk.config.get(CONFIG_SKIP_STATIC, DEFAULT_SKIP_STATIC))


def force_sync() -> bool:
    return tk.asbool(tk.config.get(CONFIG_FOCE_SYNC, DEFAULT_FORCE_SYNC))


def public_path() -> str:
    return tk.config.get(CONFIG_PUBLIC_PATH, DEFAULT_PUBLIC_PATH)


def drupal_version() -> str:
    return tk.config.get(CONFIG_DRUPAL_VERSION, DEFAULT_DRUPAL_VERSION)


def extra_fields() -> list[str]:
    return tk.aslist(tk.config.get(CONFIG_EXTRA_FIELDS, DEFAULT_EXTRA_FIELDS))


def same_id() -> bool:
    return tk.asbool(tk.config.get(CONFIG_SAME_ID))


def synchronization_enabled() -> bool:
    return tk.asbool(tk.config.get(CONFIG_SYNCHRONIZATION_ENABLED))


def static_host() -> str | None:
    return tk.config.get(CONFIG_STATIC_HOST)


def inherit_admin_role() -> bool:
    return tk.asbool(tk.config.get(CONFIG_INHERIT_ADMIN_ROLE))


def admin_role_name() -> str:
    return tk.config.get(CONFIG_ADMIN_ROLE_NAME, DEFAULT_ADMIN_ROLE)


def db_url() -> str:
    return tk.config.get(CONFIG_DB_URL)
