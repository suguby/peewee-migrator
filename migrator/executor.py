# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import codecs
import hashlib
import json
import os
import sys
import time

from migrator.code_generator import CodeGenerator
from migrator.collector import ChangesCollector
from migrator.db_inspector import Inspector

__all__ = ['Executor']


def extend_path(path, index=0):
    for p in reversed(path.split(':')):
        if p not in sys.path:
            sys.path.insert(index, p)


class Executor(object):
    CodeGenerator = CodeGenerator
    STATUS_APPLIED = 'applied'
    STATUS_AVAILABLE = 'available'
    REQUIRED_FILE = 'required.json'

    def __init__(self, config):
        self.config = config
        # Необходимо для корректной работы
        extend_path(config.get_setting(config.MIGRATOR_SYS_PATH), 1)
        self.migrations_in_path = False

    def _extend_migrations(self):
        if not self.migrations_in_path:
            extend_path(self.config.get_setting(self.config.MIGRATOR_MIGRATIONS_DIR), 0)
            self.migrations_in_path = True

    def import_migration(self, migration):
        return __import__(migration['import'])

    def get_migrations(self):
        migrations_dir = self.config.get_setting(self.config.MIGRATOR_MIGRATIONS_DIR)
        # Необходимо для работы __import__
        self._extend_migrations()

        for f in os.listdir(migrations_dir):
            if f.startswith('migration_') and f.endswith('.py'):
                revision = f.split('migration_', 1)[-1].rsplit('.py', 1)[0]
                yield self.fetch_migration(revision)

    def get_migrations_by_hash(self, base_hash, migrations=None):
        migrations = self.get_migrations() if migrations is None else migrations
        return [x for x in migrations if x['hash'].startswith(base_hash)]

    def fetch_migration(self, revision):
        self._extend_migrations()
        migration = __import__('migration_{}'.format(revision))
        return {
            'time': migration.MIGRATION_TIME,
            'name': migration.MIGRATION_NAME,
            'hash': revision,
            'file': 'migration_{}.py'.format(revision),
            'import': 'migration_{}'.format(revision),
            'dependencies': migration.MIGRATION_DEPENDENCIES,
            # Примененность
            'status': self.check_status(revision),
            # Обязательность
            'required': self.check_required_position(revision)
        }

    def apply(self, migration, fake=False):
        if not fake:
            _module = self.import_migration(migration)
            _module.up(config=self.config)
        self.make_applied(migration['hash'])

    def revert(self, migration, fake=False):
        if not fake:
            _module = self.import_migration(migration)
            _module.down(self.config)
        self.unmake_applied(migration['hash'])

    def get_applied(self):
        migrations_dir = self.config.get_setting(self.config.MIGRATOR_MIGRATIONS_DIR)
        # TODO: Добавить бэкенд сохранения в БД
        try:
            with codecs.open(os.path.join(migrations_dir, '.applied.json'), 'r', 'utf-8') as f:
                return json.loads(f.read())
        except:
            return []

    def get_required(self):
        migrations_dir = self.config.get_setting(self.config.MIGRATOR_MIGRATIONS_DIR)
        try:
            with codecs.open(os.path.join(migrations_dir, self.REQUIRED_FILE), 'r', 'utf-8') as f:
                return json.loads(f.read())
        except:
            return []

    def make_required(self, revision, after=None):
        required = self.get_required()
        position = len(required)  # Последним
        if after is not None:
            try:
                position = required.index(after) + 1
            except ValueError:
                pass
        required.insert(position, revision)
        self.save_required_fs(required)

    def make_applied(self, revision):
        applied = set(self.get_applied())
        applied.add(revision)
        self.save_applied_fs(applied)

    def unmake_applied(self, revision):
        applied = set(self.get_applied())
        applied.remove(revision)
        self.save_applied_fs(applied)

    def save_applied_fs(self, applied):
        # TODO: Добавить бэкенд сохранения в БД
        migrations_dir = self.config.get_setting(self.config.MIGRATOR_MIGRATIONS_DIR)
        with codecs.open(os.path.join(migrations_dir, '.applied.json'), 'w', 'utf-8') as f:
            f.write(json.dumps(list(applied)))

    def save_required_fs(self, required):
        migrations_dir = self.config.get_setting(self.config.MIGRATOR_MIGRATIONS_DIR)
        with codecs.open(os.path.join(migrations_dir, self.REQUIRED_FILE), 'w', 'utf-8') as f:
            f.write(json.dumps(required))

    def check_status(self, revision):
        applied = self.get_applied()

        return self.STATUS_APPLIED if revision in applied else self.STATUS_AVAILABLE

    def check_required_position(self, revision):
        required = self.get_required()

        try:
            return required.index(revision)
        except ValueError:
            return None

    def check_dependencies(self, migration):
        return all([self.check_status(dep) == self.STATUS_APPLIED for dep in migration['dependencies']])

    def get_db_obj(self):
        return self.config.get_db()

    def check_migrations_package(self):
        init_path = os.path.join(self.config.get_setting(self.config.MIGRATOR_MIGRATIONS_DIR), '__init__.py')
        if not os.path.exists(init_path):
            with codecs.open(init_path, 'w') as f:
                f.write('')

    def make_empty_migration(self, migration_name=None):
        # TODO: сделать генерацию по готовому шаблону, без self.migrate
        i = Inspector(models_path=self.config.get_models_paths(), excluded_models=self.config.get_excluded())
        current_models = list(i.inspect_models())
        c = CodeGenerator(current_models)
        imports, models, proxies = c.clses_code()
        new = {x['name']: x for x in c.clses_json()}
        return self.migrate(imports, models, proxies, new, new, migration_name=migration_name)

    def migrate_from_migration(self, migration=None, migration_name=None):
        excluded_models = self.config.get_excluded()
        # Получение информации о предыдущем состоянии из моделй
        i = Inspector(models_path=[migration['import']], excluded_models=excluded_models)
        old_models = list(i.inspect_models())
        old = {x['name']: x for x in CodeGenerator(old_models).clses_json()}
        # Получение информации о текущем состоянии из моделей
        i = Inspector(models_path=self.config.get_models_paths(), excluded_models=excluded_models)
        current_models = list(i.inspect_models())
        new = {x['name']: x for x in CodeGenerator(current_models).clses_json()}
        # генерация кода старых и новых моделей
        c = CodeGenerator(current_models + old_models)
        imports, models, proxies = c.clses_code()
        return self.migrate(
            imports, models, proxies, new, old, migration_name=migration_name, dependencies=[migration]
        )

    def migrate_from_db(self, migration_name=None):
        excluded_models = self.config.get_excluded()
        i = Inspector(models_path=self.config.get_models_paths(), excluded_models=excluded_models)
        # Получение информации о текущем состоянии из моделей
        current_models = list(i.inspect_models())
        new = {x['name']: x for x in CodeGenerator(current_models).clses_json()}
        # Получение информации о состоянии из базы данных
        db_models = list(i.inspect_database(self.get_db_obj()))
        old = {x['name']: x for x in CodeGenerator(db_models).clses_json()}
        # генерация кода старых и новых моделей
        current_models_tables = [m[1] for m in current_models]
        for db_model in db_models:
            if db_model[1] not in current_models_tables:
                current_models.append(db_model)
        c = CodeGenerator(current_models)
        imports, models, proxies = c.clses_code()
        return self.migrate(imports, models, proxies, new, old, migration_name=migration_name)

    def migrate(self, imports, models, proxies, new, old, migration_name=None, dependencies=None):
        up_migration = self._get_migration_changes(new=new, old=old)
        up = self.CodeGenerator.changes_code(up_migration, indent=4)
        down_migration = self._get_migration_changes(new=old, old=new)
        down = self.CodeGenerator.changes_code(down_migration, indent=4)
        return self.make_migration(
            imports, models, up=up, down=down, migration_name=migration_name, proxies=proxies,
            dependencies=dependencies
        )

    def _get_migration_changes(self, new, old):
        collector = ChangesCollector()
        # Построение таблицы соответствий
        model_matches = collector.get_table_matches(new, old)
        # Операции миграции
        migration = {
            # Базовые операции: создание и удаление таблиц
            'drop': [x for x in old.keys() if x not in model_matches.values()],
            'create': [x for x in new.keys() if x not in model_matches.keys()],
            # Наполняемые данные
            'rename': [],
            'fields': {
                'rename': [],
                'create': [],
                'drop': [],
                'index': [],
                'null': []
            }
        }
        for new_model_name, old_model_name in model_matches.items():
            new_model = new[new_model_name]
            old_model = old[old_model_name]
            # Обработка случая переименования таблицы
            if new_model['table'] != old_model['table']:
                migration['rename'].append((old_model['table'], new_model['table']))

            # Обработка полей
            new_fields = {x['name']: x for x in new[new_model_name]['fields']}
            old_fields = {x['name']: x for x in old[old_model_name]['fields']}

            field_matches = collector.get_field_matches(new[new_model_name]['fields'], new_fields, old_fields)
            # Создание и удаление полей
            migration['fields']['drop'].extend(
                collector.get_columns_to_drop(new_fields, old_fields, new_model, old_model, field_matches)
            )
            migration['fields']['create'].extend(
                collector.get_columns_to_create(new_fields, old_fields, new_model, old_model, field_matches)
            )

            for new_field_name, old_field_name in field_matches.items():
                new_field = new_fields[new_field_name]
                old_field = old_fields[old_field_name]
                # Обработка индексов
                migration['fields']['index'].extend(
                    collector.get_field_indexes(new_field, old_field, new_model, old_model))
                # Обработка null
                migration['fields']['null'].extend(collector.get_field_null(new_field, old_field, new_model, old_model))
                # Обработка переименований полей
                migration['fields']['rename'].extend(
                    collector.get_field_rename(new_field, old_field, new_model, old_model))

        return migration

    def make_migration(
        self, imports, models, up=None, down=None, migration_name=None, proxies=None, dependencies=None
    ):

        self.check_migrations_package()

        migration_time = int(time.time())
        migration_hash = hashlib.md5(str(migration_time).encode('utf-8')).hexdigest()

        migration_kwargs = locals()
        migration_kwargs.pop('self', None)

        migration_path = os.path.join(
            self.config.get_setting(self.config.MIGRATOR_MIGRATIONS_DIR),
            'migration_{}.py'.format(migration_hash)
        )
        migration_code = self.CodeGenerator.migration_code(**migration_kwargs)

        with codecs.open(migration_path, 'w', 'utf-8') as f:
            f.write(migration_code)

        return migration_path

