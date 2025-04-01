import click

import ckan.model as model
from . import utils


def get_commands():
    return [drupal_idp]


@click.group(short_help="ckanext-drupal-idp CLI")
def drupal_idp():
    """ """
    pass


@drupal_idp.group()
def user():
    """User management"""
    pass


@user.command()
def list():
    """List all users with DrupalID"""
    users = model.Session.query(model.User).filter(
        model.User.plugin_extras.has_key("drupal_idp")
    )
    for user in users:
        click.echo(f"{user.name}:")
        extras = user.plugin_extras["drupal_idp"]
        click.echo(f"\tID: {extras['id']}")
        click.echo(f"\tRoles: {', '.join(extras['roles'])}")
        click.echo(f"\tEmail: {extras['email']}")
        click.echo()


@user.command()
def cookie_name():
    """Print expected name of the authentication cookie."""
    click.echo(utils.session_cookie_name())
