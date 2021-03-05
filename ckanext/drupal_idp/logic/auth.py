import ckan.plugins.toolkit as tk

_auth_functions = {}

def auth_function(func):
    _auth_functions[f'drupal_idp_{func.__name__}'] = func
    return func


def get_auth_functions():
    return _auth_functions


@auth_function
@tk.auth_disallow_anonymous_access
def user_show(context, data_dict):
    return {'success': False, 'msg': tk._('Users are not allowed to use DrupalID')}
