# -*- coding: utf-8 -*-
import codecs
import hashlib
import json
import os
import time

import peewee
from playhouse.shortcuts import model_to_dict, dict_to_model

from migrator.code_generator import CodeGenerator
from migrator.db_inspector import Inspector
from migrator.executor import Executor
from migrator.utils import SafeEncoder, pickle_hook


class FixtureLoader(object):
    #  Pycharm stub
    _table = None
    _with_schema = None

    def __init__(self, config):
        self.config = config
        self.executor = Executor(config=config)
        self.db = self.config.get_db()

    def make_data_migration(self, migration_name, only_models=None):
        only_models = only_models.split(',') if only_models else []
        inspector = Inspector(excluded_models=self.config.get_excluded())

        data_to_save = {}
        for model_class in inspector.get_database_models(self.db):
            class_name = model_class.__name__
            if only_models and class_name not in only_models:
                continue
            data = [model_to_dict(obj) for obj in model_class.select()]
            if data:
                data_to_save[class_name] = data

        migration_time = int(time.time())
        migration_hash = hashlib.md5(str(migration_time).encode('utf-8')).hexdigest()
        fixture_path = os.path.join(self.config.get_setting(self.config.MIGRATOR_MIGRATIONS_DIR), 'fixtures')
        os.makedirs(fixture_path,  exist_ok=True)
        fixture_file_name = os.path.join(fixture_path, '{}.json'.format(migration_hash))
        with codecs.open(fixture_file_name, 'w', 'utf-8') as f:
            f.write(json.dumps(data_to_save, cls=SafeEncoder, sort_keys=True, ensure_ascii=False, indent=1))

        up = [
            'from migrator import load_data',
            '',
            'models = dict({})'.format(', '.join(['{}={}'.format(k, k) for k in data_to_save.keys()])),
            "load_data(config, "
            "migration_hash='{migration_hash}', "
            "models=models"
            ")".format(
                config=self.config,
                migration_hash=migration_hash,
            ),
        ]

        db_models = list(inspector.inspect_database(self.db))
        c = CodeGenerator(db_models)
        imports, models, proxies = c.clses_code()

        return self.executor.make_migration(
            imports, models, up=up, down=None, migration_name=migration_name, proxies=proxies
        )

    def load_data(self, migration_hash, models):
        migrations_path = self.config.get_setting(self.config.MIGRATOR_MIGRATIONS_DIR)
        fixture_path = os.path.join(migrations_path, 'fixtures', migration_hash + '.json')
        if not os.path.exists(fixture_path):
            raise Exception('No fixture file at the {}'.format(fixture_path))
        with codecs.open(fixture_path, 'r', 'utf-8') as f:
            data = f.read()
        fixture = json.loads(data, encoding='utf-8', object_hook=pickle_hook)
        self._preload()
        for model_name, model_class in models.items():
            data = fixture.get(model_name, [])
            if not data:
                continue
            self._model_preload(model_class)
            for row in data:
                instance = dict_to_model(model_class, row)
                exist = model_class.select().where(instance._pk_expr()).first()
                instance.save(force_insert=not bool(exist))
            self._model_postload(model_class)
        self._postload()

    def _preload(self):
        if self.config.db_type == 'mysql':
            self.db.execute_sql('SET foreign_key_checks = 0;')

    def _postload(self):
        if self.config.db_type == 'mysql':
            self.db.execute_sql('SET foreign_key_checks = 1;')

    def _model_preload(self, model_class):
        if self.config.db_type == 'postgres':
            schema = ''
            if model_class._meta.schema:
                schema = '{}.'.format(model_class._meta.schema)
            self._with_schema = lambda x: '{}{}'.format(schema, x)
            self._table = self._with_schema(model_class._meta.db_table)
            model_class.raw('ALTER TABLE {} DISABLE TRIGGER USER;'.format(self._table)).execute()

    def _model_postload(self, model_class):
        if self.config.db_type == 'postgres':
            model_class.raw('ALTER TABLE {} ENABLE TRIGGER USER;'.format(self._table)).execute()
            seq = self._with_schema('{}_{}_seq'.format(model_class._meta.db_table, model_class._meta.primary_key.db_column))
            model_class.raw(
                "SELECT setval('{seq}', (SELECT COALESCE(MAX(id)+(SELECT increment_by FROM {seq}), "
                "(SELECT min_value FROM {seq})) FROM {table}), false)".format(seq=seq, table=self._table)
            ).execute()
        elif self.config.db_type == 'mysql':
            max_val = model_class.select(peewee.fn.Max(model_class._get_pk_value(model_class))).scalar()
            model_class.raw('ALTER TABLE {table} AUTO_INCREMENT = {value};'.format(
                table=model_class._meta.db_table,
                value=max_val+1)
            ).execute()


def load_data(config, migration_hash, models):
    loader = FixtureLoader(config)
    loader.load_data(migration_hash, models)
