# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import json


__all__ = ['CodeGenerator']


class CodeGenerator(object):
    PROXY_PREFIX = 'MigratorProxy__'
    MIGRATION_TEMPLATE = '''# -*- coding: utf-8 -*-
{imports}
from playhouse.migrate import migrate


MIGRATION_NAME = {migration_name}
MIGRATION_TIME = {migration_time}
MIGRATION_DEPENDENCIES = {migration_dependencies}


proxy_db = peewee.Proxy(){proxy_fields}


class BaseModel(peewee.Model):
    class Meta:
        database = proxy_db


{models}{proxy_fields_init}


def up(db, migrator):
    proxy_db.initialize(db)
{up}


def down(db, migrator):
    proxy_db.initialize(db)
{down}
'''

    def __init__(self, models):
        self.models = models

    class Builder(object):
        def __init__(self, indent=0, indent_step=4):
            self.indent = indent
            self.indent_step = indent_step
            self.lines = []

        def tab(self):
            self.indent += self.indent_step
            return self

        def un_tab(self):
            self.indent -= self.indent_step
            return self

        def write_line(self, text):
            self.lines.append('{}{}'.format(' ' * self.indent, text))
            return self

        @property
        def code(self):
            return '\n'.join(self.lines)

    @classmethod
    def _join_lines_with_indent(cls, lines, indent=4):
        return '\n'.join(['{}{}'.format(' ' * indent, x) for x in lines])

    @classmethod
    def _get_import_by_path(cls, path):
        return '.'.join(path.split('.')[:-1])

    def clses_code(self):
        builder = self.Builder()
        to_import = {'peewee'}
        models_str = []
        proxies_str = set()
        for model, db_table, fields in self.models:
            builder.write_line('class {}(BaseModel):'.format(model))
            for field in fields:
                to_import.add(self._get_import_by_path(field['path']))
                params = []
                if field['params']['index'] and not field['params']['unique']:
                    params.append('index=True')
                if field['params']['unique']:
                    params.append('unique=True')
                if field['params']['null']:
                    params.append('null=True')
                db_field = field['params'].get('initial_kwargs', {}).get('db_field', field['column'])
                if db_field and db_field != field['name']:
                    params.append('db_column={}'.format(db_field.__repr__()))
                to_field = field['params'].get('initial_kwargs', {}).get('to_field', {})
                if to_field and to_field['column'] != 'id':
                    params.append('to_field={}'.format(to_field['column'].__repr__()))
                if field['params'].get('initial_kwargs'):
                    rel = field['params']['initial_kwargs'].get('rel_model', None)
                    if rel:
                        if rel == model:
                            rel = "'self'"
                        else:
                            proxies_str.add(rel)
                            rel = '{}{}'.format(self.PROXY_PREFIX, rel)
                        params.insert(0, rel)
                        # TODO: Попробовать разобраться здесь, добавляя только данные, которые можно сериализовать
                        # for k, v in field['params']['initial_kwargs'].iteritems():
                        #     params.append('{}={}'.format(k, v))
                field_code = '{} = {}({})'.format(field['name'], field['path'], ', '.join(params))
                builder.tab().write_line(field_code).un_tab()
            builder.write_line('').tab().write_line('class Meta:')
            builder.tab().write_line('db_table = {}'.format(db_table.__repr__())).un_tab().un_tab()
            builder.write_line('').write_line('')
        models_str.append(builder.code)
        imports_str = ['import {}'.format(x) for x in to_import]
        return imports_str, models_str, sorted(proxies_str)

    def clses_json(self):
        models_json = []
        for model, db_table, fields in self.models:
            model_json = {'name': model}
            fields_json = []
            imports = set()
            for field in fields:
                import_path = self._get_import_by_path(field['path'])
                params = {}
                if field['params']['index'] and not field['params']['unique']:
                    params['index'] = True
                if field['params']['unique']:
                    params['unique'] = True
                if field['params']['null']:
                    params['null'] = True
                db_field = field['params'].get('initial_kwargs', {}).get('db_field', field['column'])
                if db_field and db_field != field['name']:
                    params['db_field'] = db_field
                if field['params'].get('initial_kwargs'):
                    rel = field['params']['initial_kwargs'].get('rel_model', None)
                    if rel:
                        if rel == model:
                            rel = "'self'"
                        params['__args'] = rel
                field_json = {
                    'path': field['path'], 'params': params, 'name': field['name']
                }
                if import_path != 'peewee':
                    field_json['import'] = import_path
                    imports.add(import_path)
                fields_json.append(field_json)
            model_json.update({'table': db_table, 'fields': fields_json})
            if imports:
                model_json['imports'] = list(imports)
            models_json.append(model_json)
        return sorted(models_json, key=lambda x: x['name'])

    @classmethod
    def changes_code(cls, migration, indent=0):
        builder = cls.Builder(indent=indent)
        up, down = [], ['pass']

        # Создание таблиц
        if migration['create']:
            builder.write_line('').write_line('# Tables creation')
            for model in migration['create']:
                builder.write_line('{model}.create_table()'.format(model=model))

        # Удаление таблиц
        if migration['drop']:
            builder.write_line('').write_line('# Tables deletion')
            for model in migration['drop']:
                builder.write_line('{model}.drop_table()'.format(model=model))

        # Переименование таблиц
        pass

        # Создание полей
        if migration['fields']['create']:
            builder.write_line('').write_line('# Fields creation')
            builder.write_line('migrate(').tab()
            for table, db_field, field in migration['fields']['create']:
                builder.write_line(
                    'migrator.add_column({}, {}, {}),'.format(table.__repr__(), db_field.__repr__(), field)
                )

            builder.un_tab().write_line(')')

        # Удаление полей
        if migration['fields']['drop']:
            builder.write_line('').write_line('# Drop fields')
            builder.write_line('migrate(').tab()
            for table, db_field in migration['fields']['drop']:
                builder.write_line('migrator.drop_column({}, {}),'.format(table.__repr__(), db_field.__repr__()))
            builder.un_tab().write_line(')')

        # Переименование полей
        pass

        # Удаление индексов
        to_drop = [x for x in migration['fields']['index'] if x[0] == 'drop']
        if to_drop:
            builder.write_line('').write_line('# Drop fields')
            builder.write_line('migrate(').tab()
            for action, table, db_field in to_drop:
                builder.write_line('migrator.drop_index({}, {}),'.format(table.__repr__(), db_field.__repr__()))
            builder.un_tab().write_line(')')

        # Создание индексов
        to_create = [x for x in migration['fields']['index'] if x[0] == 'add']
        unique = [x for x in to_create if x[-1]]
        index = [x for x in to_create if not x[-1]]
        if index:
            builder.write_line('').write_line('# Create indexes')
            builder.write_line('migrate(').tab()
            for action, table, db_field, is_uniq in index:
                builder.write_line(
                    'migrator.add_index({}, ({},), False),'.format(table.__repr__(), db_field.__repr__())
                )
            builder.un_tab().write_line(')')
        if unique:
            builder.write_line('').write_line('# Create unique indexes')
            builder.write_line('migrate(').tab()
            for action, table, db_field, is_uniq in index:
                builder.write_line(
                    'migrator.add_index({}, ({},), True)),'.format(table.__repr__(), db_field.__repr__())
                )
            builder.un_tab().write_line(')')

        up = [builder.code]

        return up, down

    @classmethod
    def migration_code(
            cls, imports, models, old_data, up=None, down=None, migration_name=None,
            proxies=None, dependencies=None, migration_time=None, migration_hash=None
    ):
        if migration_name is None:
            migration_name = 'Миграция {}'.format(migration_hash)
        if dependencies is None:
            migration_dependencies = []
        else:
            migration_dependencies = '[{}]'.format(', '.join([x['hash'].__repr__() for x in dependencies]))
        if up is None:
            up = ['pass']
        if down is None:
            down = ['pass']
        up = cls._join_lines_with_indent(up)
        down = cls._join_lines_with_indent(down)

        # Обработка прокси
        proxy_fields = []
        proxy_fields_init = []
        for proxy in (proxies or []):
            proxy_fields.append('{}{} = peewee.DeferredRelation()'.format(cls.PROXY_PREFIX, proxy))
            proxy_fields_init.append('{prefix}{proxy}.set_model({proxy})'.format(prefix=cls.PROXY_PREFIX, proxy=proxy))
        proxy_fields = '\n{}'.format('\n'.join(proxy_fields)) if proxy_fields else ''
        proxy_fields_init = '\n{}'.format('\n'.join(proxy_fields_init)) if proxy_fields_init else ''

        return cls.MIGRATION_TEMPLATE.format(
            up=up, down=down, imports='\n'.join(imports), models='\n\n\n'.join(models),
            old_data=json.dumps(old_data, indent=4), migration_name=migration_name.__repr__(),
            migration_time=migration_time, proxy_fields=proxy_fields, proxy_fields_init=proxy_fields_init,
            migration_dependencies=migration_dependencies
        )
