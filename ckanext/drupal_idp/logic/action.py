from __future__ import annotations

import ckan.plugins.toolkit as tk

from ckanext.toolbelt.decorators import Collector
import ckanext.drupal_idp.utils as utils

action, get_actions = Collector("drupal_idp").split()



@action
@tk.side_effect_free
def user_show(context, data_dict):
    tk.check_access('drupal_idp_user_show', dict(context), data_dict)
    id: utils.DrupalId = tk.get_or_bust(data_dict, 'id')
    User = context['model'].User
    user = (
        context['session'].query(User.id)
        .filter(User.plugin_extras["drupal_idp"]["id"].astext == str(id))
        .one_or_none()
    )
    if user is None:
        raise tk.ObjectNotFound(tk._(f'DrupalId({id}) not found'))
    data_dict['id'] = user.id
    return tk.get_action("user_show")(context, data_dict)


@action("user_show")
@tk.side_effect_free
@tk.chained_action
def user_show(next_, context, data_dict):
    user = next_(context, data_dict)
    if user["image_display_url"]:
        return user
    extras = context["model"].User.get(user["id"]).plugin_extras or {}
    drupal_idp = extras.get("drupal_idp") or {}
    url = drupal_idp.get("avatar")

    if not url:
        return user

    host = tk.config.get(utils.CONFIG_STATIC_HOST)
    if host and not url.startswith("http"):
        url = "//" + host.rstrip("/") + url

    user["image_display_url"] = url

    return user
