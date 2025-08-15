from __future__ import annotations

from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from flask import Blueprint
import ckan.plugins.toolkit as tk

from . import config

bp = Blueprint("drupal_idp", __name__)


def get_blueprints():
    return [bp]


@bp.route("/user/login/drupal-idp-redirect")
def redirect_to_drupal_login():
    login_url = tk.config.get("ckanext.drupal_idp.login_url", "/user/login")

    if config.keep_destination():
        came_from = tk.request.args.get("came_from")

        parsed = urlparse(login_url)
        qs = parse_qs(parsed.query)
        if came_from:
            qs["destination"] = [came_from]
            login_url = urlunparse(parsed._replace(query=urlencode(qs, True)))

    return tk.redirect_to(login_url)
