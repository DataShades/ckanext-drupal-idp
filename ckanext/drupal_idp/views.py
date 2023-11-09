from __future__ import annotations

from flask import Blueprint
import ckan.plugins.toolkit as tk
bp = Blueprint("drupal_idp", __name__)


def get_blueprints():
    return [bp]

@bp.route("/user/login/drupal-idp-redirect")
def redirect_to_drupal_login():
    login_url = tk.config.get("ckanext.drupal_idp.login_url", "/user/login")
    return tk.redirect_to(login_url)
