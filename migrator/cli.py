# -*- coding: utf-8 -*-

import click
import codecs
import datetime
import gettext
import sys
import tabulate
import os

from migrator.config import Config
from migrator.executor import Executor

# Установка локализации
translation = gettext.translation('migrator_cli', './locale', fallback=True)
if sys.version_info > (3,):
    _ = translation.gettext
    translation.install()
else:
    _ = translation.ugettext
    translation.install(unicode=True)


def choices_prompt(message, choices):
    return click.prompt(
        u'{}\n{}'.format(
            u'\n'.join([u'{} - {}'.format(k, v) for k, v in sorted(choices.items(), key=lambda x: x[0])]),
            message
        ),
        default='0', type=click.Choice(sorted(choices.keys())), show_default=True
    )


def halt(messgae):
    click.echo(messgae)
    sys.exit(1)


def get_one_revision(migrator, rev):
    revisions = migrator.get_migrations_by_hash(rev)
    if not revisions:
        halt(_(u'Revision {} not found.').format(rev))
    if len(revisions) > 1:
        halt(_(u'Revision {} has too much matches ({}).').format(rev, len(revisions)))
    return revisions[0]


@click.group()
@click.option('-c', '--config', type=click.Path(), default='migrator.cfg')
@click.pass_context
def cli(ctx, config):
    config = os.path.realpath(config)
    cfg = Config()
    ctx.obj = ctx.obj or {}
    if os.path.exists(config):
        cfg.load(config)
        ctx.obj['config_path'] = config
    else:
        cfg.make_default()
        ctx.obj['config_path'] = None
    ctx.obj.update({'cfg': cfg})


@cli.command()
@click.option('--type', 'db_type_arg', default=None)
@click.option('--name', 'db_name_arg', default=None)
@click.option('--user', 'db_user_arg', default=None)
@click.option('--password', 'db_password_arg', default=None)
@click.option('--host', 'db_host_arg', default=None)
@click.option('--port', 'db_port_arg', default=None)
@click.option('--dir', 'migrations_dir_arg', default=None)
@click.option('--project', 'project_dir_arg', default=None)
@click.option('--models', 'models_path_arg', default=None)
@click.option('--excluded', 'models_excluded_arg', default=None)
@click.option('--force', default=False, is_flag=True)
@click.pass_context
def create_config(
        ctx, db_type_arg, db_name_arg, db_user_arg, db_password_arg, db_host_arg, db_port_arg,
        migrations_dir_arg, project_dir_arg, models_path_arg, models_excluded_arg, force
):
    config_path = ctx.obj['config_path'] or 'migrator.cfg'
    ask_edit = all(
        x is None for x in (
            db_type_arg, db_name_arg, db_user_arg, db_password_arg, db_host_arg, db_port_arg,
            migrations_dir_arg, project_dir_arg, models_path_arg, models_excluded_arg
        )
    )
    if os.path.exists(config_path):
        if not force and not click.confirm(_(u'Config already exists. Overwrite?'), default=False):
            return
    db_types = {'0': 'postgres', '1': 'sqlite', '2': 'mysql'}

    if db_type_arg is None:
        result = choices_prompt(_(u'Database type'), db_types)
        db_type = db_types[result]
    else:
        db_type = db_type_arg
    click.echo(db_type)
    db_name = (
        click.prompt(_(u'Database'), default='peewee{}'.format('.db' if db_type == 'sqlite' else ''))
        if db_name_arg is None else db_name_arg
    )
    if db_type == 'sqlite':
        db_url = 'sqlite:///{}'.format(db_name)
    else:
        user = click.prompt(_(u'User'), default='peewee') if db_user_arg is None else db_user_arg
        password = click.prompt(_(u'Password'), hide_input=True) if db_password_arg is None else db_password_arg
        host = click.prompt(_(u'Host'), default='127.0.0.1') if db_host_arg is None else db_host_arg
        port = (
            click.prompt(_(u'Port'), default='5432' if db_type == 'postgres' else '3306')
            if db_port_arg is None else db_port_arg
        )
        db_url = '{}://{}:{}@{}:{}/{}'.format(db_type, user, password, host, port, db_name)

    default_path = os.path.abspath('.')
    migrations_dir = (
        click.prompt(
            _(u'Migrations directory'), default=os.path.join(default_path, 'migrations'), type=click.Path(
                exists=True, file_okay=False, writable=True, readable=True, resolve_path=True
            )
        ) if migrations_dir_arg is None else migrations_dir_arg
    )
    project_dir = (
        click.prompt(
            _(u'Project directory (For PYTHON_PATH)'), default=default_path, type=click.Path(
                exists=True, file_okay=False, writable=False, readable=True
            )
        ) if project_dir_arg is None else project_dir_arg
    )

    models_path = (
        click.prompt(_(u'Models path (Comma separated)'), default='app.models')
        if models_path_arg is None else models_path_arg
    )

    excluded_models = (
        click.prompt(_(u'Excluded models by name (Comma separated)'), default='')
        if models_excluded_arg is None else models_excluded_arg
    )

    # Тут записать все в новый конфиг
    cfg = Config()
    cfg.update({
        cfg.BASE_SECTION: {
            cfg.MIGRATOR_DB_URL: db_url,
            cfg.MIGRATOR_DB_TYPE: db_type,
            cfg.MIGRATOR_PROJECT_DIR: project_dir,
            cfg.MIGRATOR_MIGRATIONS_DIR: migrations_dir,
            cfg.MIGRATOR_MODELS_PATH: models_path,
            cfg.MIGRATOR_EXCLUDED_MODELS: excluded_models
        }
    })

    config = cfg.to_string_io().getvalue()

    if ask_edit and click.confirm(_(u'Edit config?'), default=True):
        edited = click.edit(config)
        if edited is not None:  # None - если редактирование отменено
            config = edited
    with codecs.open(config_path, 'w', 'utf-8') as f:
        f.write(config)
    click.echo(_(u'Config successfully saved!'))


@cli.command('make')
@click.option('--from', 'migration_type', default='db', type=click.Choice(['db', 'last', 'rev', 'empty']))
@click.option('--rev', default=None)
@click.option('--name', default=None)
@click.pass_context
def make_migration(ctx, migration_type, rev, name):
    migrator = Executor(ctx.obj['cfg'])
    if rev is None and migration_type == 'rev':
        halt(_(u'--rev param required'))
    migration_name = (click.prompt(_(u'Migration title')) or None) if name is None else name

    if migration_type == 'empty':
        migrator.make_empty_migration(migration_name=migration_name)
    if migration_type == 'db':
        migrator.migrate_from_db(migration_name=migration_name)
        return
    if migration_type == 'last':
        last = sorted(migrator.get_migrations(), key=lambda x: -x['time'])
        if not last:
            halt(_(u'There are no latest migration.'))
        migrator.migrate_from_migration(last[0], migration_name=migration_name)
        return
    if migration_type == 'rev':
        revisions = migrator.get_migrations_by_hash(rev)
        if not revisions:
            click.echo(_(u'Revision {} not found.').format(rev))
        if len(revisions) > 1:
            halt(_(u'Revision {} has too much matches ({}).').format(rev, len(revisions)))
        migrator.migrate_from_migration(revisions[0], migration_name=migration_name)
        return


@cli.command('apply')
@click.option('--force', default=False, is_flag=True)
@click.argument('rev')
@click.pass_context
def apply_migration(ctx, force, rev):
    migrator = Executor(ctx.obj['cfg'])
    revision = get_one_revision(migrator, rev)
    if migrator.check_status(revision['hash']) == migrator.STATUS_APPLIED:
        if not force and not click.confirm(_(u'Migration already applied. Repeat?'), default=False):
            halt(_(u'Abort'))
    if not migrator.check_dependencies(revision):
        not_applied = [x for x in revision['dependencies'] if migrator.check_status(x) != migrator.STATUS_APPLIED]
        halt(_(u'Migration dependencies not applied: {}').format(u','.join(not_applied)))
    migrator.apply(revision)
    click.echo(_(u'Migration {} applied successfully!').format(revision['hash']))


@cli.command('list')
@click.option('--sort', default='time', type=click.Choice(['name', 'time', 'hash', 'status']))
@click.option('--reverse', default=False, is_flag=True)
@click.pass_context
def migrations_list(ctx, sort, reverse):
    migrator = Executor(ctx.obj['cfg'])
    headers = [_(u'Time'), _(u'Title'), _(u'Migration'), _(u'Dependencies'), _(u'Applied'), _(u'Required')]
    rows = []
    for migration in migrator.get_migrations():
        rows.append([
            datetime.datetime.fromtimestamp(migration['time']),
            migration['name'],
            migration['hash'],
            ', '.join(migration['dependencies']) if migration['dependencies'] else _(u'No'),
            _(u'Yes') if migration['status'] == migrator.STATUS_APPLIED else _(u'No'),
            u'{}, {}'.format(_(u'Yes'), migration['required'] + 1) if migration['required'] is not None else _(u'No')
        ])
    sort_column = {'time': 0, 'name': 1, 'hash': 2, 'status': 4}[sort]
    rows = sorted(rows, key=lambda x: x[sort_column])
    if reverse:
        rows = reversed(rows)
    click.echo(tabulate.tabulate(rows, headers, tablefmt='psql'))


@cli.command('require')
@click.option('--after', default=None)
@click.argument('rev')
@click.pass_context
def mark_required(ctx, after, rev):
    migrator = Executor(ctx.obj['cfg'])
    revision = get_one_revision(migrator, rev)['hash']
    if after is not None:
        after = get_one_revision(migrator, after)['hash']
    migrator.make_required(revision, after=after)
    click.echo(_(u'Revision {} marked as required').format(revision))


@cli.command('up')
@click.pass_context
def up_required(ctx):
    migrator = Executor(ctx.obj['cfg'])
    required = migrator.get_required()
    if not required:
        halt(_(u'There are no required migrations (Empty required.json)'))

    to_apply = [rev for rev in required if migrator.check_status(rev) != migrator.STATUS_APPLIED]
    if not to_apply:
        halt(_(u'Project already up to date'))
    for rev in to_apply:
        revision = get_one_revision(migrator, rev)
        if not migrator.check_dependencies(revision):
            not_applied = [x for x in revision['dependencies'] if migrator.check_status(x) != migrator.STATUS_APPLIED]
            halt(_(u'Migration dependencies not applied: {}').format(u','.join(not_applied)))
        migrator.apply(revision)
        click.echo(_(u'Migration {} applied successfully!').format(revision['hash']))


if __name__ == '__main__':
    cli()
