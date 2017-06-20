Migrator
========

Base migrations support for peewee ORM

Installation
--------------------

pip install peewee-migrator


Create config file
--------------------

Run migrator create_config, follow instructions.

An example of the your_app.cfg::

    [migrator]
    db_url = postgres://peewee:123@127.0.0.1:5432/peewee
    migrations_dir = /path/to/your/project/migrations
    sys_path = /path/to/your/project:/path/to/external/library
    models_path = app.models
    excluded_models =

Migration management
--------------------

Interactive migrator config creation
  migrator -c your_app.cfg create_config

List your migrations
  migrator -c your_app.cfg list

Make auto migration from current DB state
  migrator -c your_app.cfg make --from db

Make auto migration from another migration
  migrator -c your_app.cfg make --from rev --rev migration_hash

Make auto migration from latest migration
  migrator -c your_app.cfg make --from last

Make empty migration (Based on current MODELS_PATH state)
  migrator -c you_app.cfg make --from empty

Apply migration
  migrator -c your_app.cfg apply migration_hash


Required migrations
-------------------

Mark migration as required
  migrator -c your_app.cfg require migration_hash

Mark migration as required after another migration
  migrator -c your_app.cfg require migration_hash --after another_hash

Apply all required migrations at once
  migrator -c your_app.cfg up_required
