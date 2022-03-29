[![Tests](https://github.com/DataShades/ckanext-drupal-idp/workflows/Tests/badge.svg?branch=main)](https://github.com/DataShades/ckanext-drupal-idp/actions)

# ckanext-drupal-idp

When Drupal's session cookie is available use it for user authentication. Create missing users, using data from Drupal's DB and synchronize(conditionally) fields when user details changed on Drupal's side.


## Requirements

* python >= 3.6
* CKAN >= 2.9


## Installation

To install ckanext-drupal-idp:

1. Activate your CKAN virtual environment, for example:

		. /usr/lib/ckan/default/bin/activate

2. Clone the source and install it on the virtualenv

		git clone https://github.com/DataShades/ckanext-drupal-idp.git
		cd ckanext-drupal-idp
		pip install -e .

3. Add `drupal-idp` to the `ckan.plugins` setting in your CKAN
   config file (by default the config file is located at
   `/etc/ckan/default/ckan.ini`).

4. Configure Drupal's DB:

		ckanext.drupal_idp.db_url = <URL>

4. Restart CKAN. For example if you've deployed CKAN with Apache on Ubuntu:

		sudo service apache2 reload


## Config settings

	# ckanext-drupal-idp
	# Defines database used by the Drupal application
	# (mandatory).
	ckanext.drupal_idp.db_url = mysql://drupal_user:drupal_pass@127.0.0.1:3306/db_name

	# Whether to make an attempt to synchronize user's details everytime
	# session is used. This may result in unauthenticated session if new name or email
	# already present in CKAN database
	# (optional, default: false).
	ckanext.drupal_idp.synchronization.enabled = true

	# Configure hostname of the drupal instance statically. Usefull for local testing with
	# manually added cookie from any accessible drupal instance
	# (optional)
	ckanext.drupal_idp.host = my.site.com

	# Whether to set sysadmin flag on the user who has Drupal's admin role
	# (optional, default: false)
	ckanext.drupal_idp.admin_role.inherit = true

	# Name of the role that grants sysadmin status
	# (optional, default: administrator)
	ckanext.drupal_idp.admin_role.name = administrator

	# When user created, set his ID to the same value as DrupalID
	# (optional, default: false)
	ckanext.drupal_idp.same_id = true

	# Custom Drupal fields that shold be synchronized as well
	# (optional, default: [])
    ckanext.drupal_idp.extra_fields = field_age field_xxx

	# Skip user identification during static requests(css/js)
	# (optional, default: false)
    ckanext.drupal_idp.skip_static = yes

## API actions

#### `drupal_idp_user_show`

##### Parameters:

    id: (mandatory) DrupalID of the user

##### Details:

Accepts mandatory `id`(DrupalID). The rest of parameters will be
passed to underlying `user_show`.

---

## Auth functions

#### `drupal_idp_user_show`

##### Details:

Checks whether user is allowed to get user details by DrupalID. At the
moment only sysadmin can pass this check.

---

## CLI

    * drupal-idp - ckanext-drupal-idp CLI
      * user - User management
        * list - List all users with DrupalID

---

## Developer installation

To install ckanext-drupal-idp for development, activate your CKAN virtualenv and
do:

    git clone https://github.com/DataShades/ckanext-drupal-idp.git
    cd ckanext-drupal-idp
    python setup.py develop
    pip install -r dev-requirements.txt


## Tests

To run the tests, do:

    pytest --ckan-ini=test.ini ckanext/drupal_idp
