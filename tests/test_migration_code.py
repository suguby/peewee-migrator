# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import

import codecs
import os
import random
import shutil
import sys
import tempfile
import unittest

import peewee

from migrator.code_generator import CodeGenerator
from migrator.config import Config
from migrator.executor import Executor

PY_FILE_TEMPLATE = '''# -*- coding: utf-8 -*-
import peewee
{code}
'''


class BaseTestCase(unittest.TestCase):
    TEST_DB_NAME = 'test.db'
    PROJECT_DIR_NAME = 'project'
    MIGRATIONS_DIR_NAME = 'migrations'
    MODELS_FILE_NAME = 'models'
    dirpath = '/tmp'

    def setUp(self):
        # Создаем временную директорию для тестов
        self.dirpath = tempfile.mkdtemp()
        # делаем случайное название проекта, дабы ре-импорты в разных тестах срабатывали
        self.current_project_name = '{}_{}'.format(self.PROJECT_DIR_NAME, random.randint(100, 999))
        self.project_dir = os.path.join(self.dirpath, self.current_project_name)
        # Создаем директории с проектом и миграциями к нему
        migrations_dir = os.path.join(self.dirpath, self.MIGRATIONS_DIR_NAME)
        os.mkdir(self.project_dir)
        os.mkdir(migrations_dir)
        # Делаем проект модулем
        ini_file = os.path.join(self.project_dir, '__init__.py')
        with codecs.open(ini_file, 'w') as f:
            f.write('')
        sys.path.insert(0, self.dirpath)
        # База данных, на которой будут проводиться проверки
        db_path = os.path.join(self.dirpath, self.TEST_DB_NAME)
        self.db = peewee.SqliteDatabase(db_path)
        self.db.connect()

    def tearDown(self):
        shutil.rmtree(self.dirpath)

    def get_config(self):
        cfg = Config()
        cfg.update({
            cfg.BASE_SECTION: {
                cfg.MIGRATOR_DB_URL: 'sqlite:///{}'.format(os.path.join(self.dirpath, self.TEST_DB_NAME)),
                # cfg.MIGRATOR_SYS_PATH: os.path.join(self.dirpath, self.PROJECT_DIR_NAME),
                cfg.MIGRATOR_SYS_PATH: self.project_dir,
                cfg.MIGRATOR_MIGRATIONS_DIR: os.path.join(self.dirpath, self.MIGRATIONS_DIR_NAME),
                cfg.MIGRATOR_MODELS_PATH: '{}.{}'.format(self.current_project_name, self.MODELS_FILE_NAME),
                cfg.MIGRATOR_EXCLUDED_MODELS: ''
            }
        })
        return cfg


class MigrationCodeTest(BaseTestCase):

    def assertValidMigration(self, path):
        migration_name = os.path.basename(path).rsplit('.py', 1)[0]
        try:
            __import__('{}.{}'.format(self.MIGRATIONS_DIR_NAME, migration_name), fromlist=['*'])
        except ImportError:
            self.fail(path)

    def migrate_from_db(self):
        migration_path = Executor(self.get_config()).migrate_from_db(migration_name='test')
        self.assertValidMigration(migration_path)
        with codecs.open(migration_path, 'r', 'utf-8') as f:
            return f.read()

    def write_models(self, code_list):
        cb = CodeGenerator.Builder()
        for code in code_list:
            if code == '<tab>':
                cb.tab()
            elif code == '<un_tab>':
                cb.un_tab()
            else:
                cb.write_line(code)
        with codecs.open('{}.py'.format(os.path.join(self.project_dir, self.MODELS_FILE_NAME)), 'w', 'utf-8') as f:
            f.write(PY_FILE_TEMPLATE.format(code=cb.code))

    def test_database_no_table(self):
        self.write_models([
            'class Message(peewee.Model):',
            '<tab>',
            'key = peewee.CharField(max_length=64)',
            'value = peewee.TextField()'
        ])

        migration_code = self.migrate_from_db()

        self.assertIn('Message.create_table()', migration_code)

    def test_database_create_field(self):
        class Message(peewee.Model):
            key = peewee.CharField(max_length=64)
            value = peewee.TextField()

            class Meta:
                database = self.db

        Message.create_table()

        self.write_models([
            'class Message(peewee.Model):',
            '<tab>',
            'key = peewee.CharField(max_length=64)',
            'value = peewee.TextField()',
            'extra = peewee.TextField()'
        ])

        migration_code = self.migrate_from_db()

        self.assertIn("migrator.add_column('message', 'extra', Message.extra)", migration_code)

    def test_database_drop_field(self):
        class Message(peewee.Model):
            key = peewee.CharField(max_length=64)
            value = peewee.TextField()
            extra = peewee.TextField()

            class Meta:
                database = self.db

        Message.create_table()

        self.write_models([
            'class Message(peewee.Model):',
            '<tab>',
            'key = peewee.CharField(max_length=64)',
            'value = peewee.TextField()'
        ])

        migration_code = self.migrate_from_db()

        self.assertIn("migrator.drop_column('message', 'extra')", migration_code)

