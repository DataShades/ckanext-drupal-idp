try:
    import ckan.plugins.toolkit as tk

    ckanext = tk.signals.ckanext
except AttributeError:
    from blinker import Namespace

    ckanext = Namespace()

after_create = ckanext.signal(u"drupal_idp:after_create")
"""Sent when a new user created.
Params:
    sender: local user ID
    user: user details
"""

after_update = ckanext.signal(u"drupal_idp:after_update")
"""Sent when user details are updated.
Params:
    sender: local user ID
    user: update details
"""
