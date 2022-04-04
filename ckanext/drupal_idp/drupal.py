from __future__ import annotations

import logging
import abc
import os
from typing import Any, Dict, Iterable, List, Optional

import sqlalchemy as sa
from sqlalchemy.exc import OperationalError, ProgrammingError

import ckan.plugins.toolkit as tk
from ckan.exceptions import CkanConfigurationException

import ckanext.drupal_idp.utils as utils

log = logging.getLogger(__name__)
CONFIG_PUBLIC_PATH = "ckanext.drupal_idp.public_path"
DEFAULT_PUBLIC_PATH = "/sites/default/files/"

def db_url() -> str:
    url = tk.config.get(utils.CONFIG_DB_URL)
    if not url:
        raise CkanConfigurationException(
            f"drupal_idp plugin requires {utils.CONFIG_DB_URL} config option."
        )
    return url


class BaseDrupal(metaclass=abc.ABCMeta):
    def __init__(self, url: str):
        self.engine = sa.create_engine(url)

    @abc.abstractmethod
    def get_user_by_sid(self, sid: str) -> Optional[Any]:
        ...

    @abc.abstractmethod
    def get_user_roles(self, uid: utils.DrupalId) -> List[str]:
        ...

    @abc.abstractmethod
    def get_avatar(self, uid: utils.DrupalId) -> Optional[str]:
        ...

    @abc.abstractmethod
    def get_field(self, uid: utils.DrupalId, field: str) -> list[Any]:
        ...

    def get_fields(self, uid: utils.DrupalId, fields: Iterable[str]) -> dict[str, list[Any]]:
        return {
            field: self.get_field(uid, field)
            for field in fields
        }


class Drupal9(BaseDrupal):
    def get_user_by_sid(self, sid: str) -> Optional[Any]:
        try:
            user = self.engine.execute(
                """
            SELECT d.name "name", d.mail email, d.uid id
            FROM sessions s
            JOIN users_field_data d
            ON s.uid = d.uid
            WHERE s.sid = %s
            """,
                [sid],
            ).first()
        except OperationalError as e:
            log.error("Cannot get a user from Drupal's database: %s", e)
            return
        # check if session has username,
        # otherwise is unauthenticated user session
        if user and user.name:
            return user

    def get_user_roles(self, uid: utils.DrupalId) -> List[str]:
        query = self.engine.execute(
            """
                 SELECT roles_target_id "name"
                 FROM user__roles
                 WHERE bundle = 'user' AND entity_id = %s
                 """,
            [uid],
        )
        return [role.name for role in query]

    def get_avatar(self, uid: utils.DrupalId):
        query = self.engine.execute(
            """
            SELECT fm.uri
            FROM file_managed fm
            JOIN user__user_picture up
            ON up.user_picture_target_id = fm.fid
            WHERE up.entity_id = %s
            LIMIT 1;
            """,
            [uid],
        )
        path = query.scalar()
        if not path:
            log.debug("User %s has no avatar", uid)
            return None

        public_prefix = "public://"
        if path.startswith(public_prefix):
            path = os.path.join(
                tk.config.get(CONFIG_PUBLIC_PATH, DEFAULT_PUBLIC_PATH).rstrip("/"),
                path[len(public_prefix):]
            )
        return path

    def get_field(self, uid: utils.DrupalId, field: str) -> list[Any]:
        try:
            query = self.engine.execute(
                f"""
                SELECT {field}_value
                FROM user__{field}
                WHERE bundle = 'user' AND entity_id = %s AND deleted = 0
                """,
                [uid],
            )
        except ProgrammingError as e:
            log.error("Cannot get a user from Drupal's database: %s", e)
            return []

        return [r[0] for r in query]




_mapping = {"9": Drupal9}


def get_adapter(version: str) -> BaseDrupal:

    return _mapping[version](db_url())
