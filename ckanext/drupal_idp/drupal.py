import logging
import abc
from typing import Any, Dict, Iterable, List, Optional

import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

import ckan.plugins.toolkit as tk
from ckan.exceptions import CkanConfigurationException

import ckanext.drupal_idp.utils as utils

log = logging.getLogger(__name__)


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


class Drupal9(BaseDrupal):
    def get_user_by_sid(self, sid: str) -> Optional[Any]:
        try:
            user = self.engine.execute(
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
            return user

    def get_user_roles(self, uid: utils.DrupalId) -> List[str]:
        query = self.engine.execute(
            """
                 SELECT roles_target_id name
                 FROM user__roles
                 WHERE bundle = 'user' AND entity_id = %s
                 """,
            [uid],
        )
        return [role.name for role in query]


_mapping = {"9": Drupal9}


def get_adapter(version: str) -> BaseDrupal:

    return _mapping[version](db_url())
