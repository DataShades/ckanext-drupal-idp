from typing import Optional

import ckan.model as model

from .utils import DrupalId


def get_helpers():
    return {
        "drupal_idp_drupal_id": drupal_id,
    }


def drupal_id(id_or_name: str) -> Optional[DrupalId]:
    user = (
        model.Session.query(
            model.User.plugin_extras["drupal_idp"]["id"].label("drupal_id")
        )
        .filter(
            (model.User.id == id_or_name) | (model.User.name == id_or_name)
        )
        .one_or_none()
    )
    if user:
        return user.drupal_id
