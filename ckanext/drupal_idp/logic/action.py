from typing import Callable, Dict

import ckan.model as model
import ckan.plugins.toolkit as tk

import ckanext.drupal_idp.utils as utils

_actions: Dict[str, Callable] = {}

def action(func: Callable):
    _actions[f'drupal_idp_{func.__name__}'] = func
    return func


def get_actions():
    return _actions


@action
@tk.side_effect_free
def user_show(context, data_dict):
    tk.check_access('drupal_idp_user_show', context, data_dict)
    id: utils.DrupalId = tk.get_or_bust(data_dict, 'id')
    user = (
        model.Session.query(model.User.id)
        .filter(model.User.plugin_extras["drupal_idp"]["id"].astext == str(id))
        .one_or_none()
    )
    if user is None:
        raise tk.ObjectNotFound(tk._(f'DrupalId({id}) not found'))
    data_dict['id'] = user.id
    return tk.get_action("user_show")(context, data_dict)
