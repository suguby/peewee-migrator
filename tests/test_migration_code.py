# -*- coding: utf-8 -*-

from __future__ import unicode_literals, absolute_import

import codecs
import os
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

    @classmethod
    def setUpClass(cls):
        # Создаем временную директорию для тестов
        cls.dirpath = tempfile.mkdtemp()

        # Создаем директории с проектом и миграциями к нему
        project_dir = cls._get_project_dir()
        migrations_dir = os.path.join(cls.dirpath, cls.MIGRATIONS_DIR_NAME)

        if not os.path.exists(project_dir):
            os.mkdir(project_dir)
        if not os.path.exists(migrations_dir):
            os.mkdir(migrations_dir)
        # Делаем проект модулем
        ini_file = os.path.join(project_dir, '__init__.py')
        if not os.path.exists(ini_file):
            with codecs.open(ini_file, 'w') as f:
                f.write('')
        sys.path.insert(0, cls.dirpath)

    @classmethod
    def _get_project_dir(cls):
        return os.path.join(cls.dirpath, cls.PROJECT_DIR_NAME)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dirpath)

    def setUp(self):
        # База данных, на которой будут проводиться проверки
        db_path = os.path.join(self.dirpath, self.TEST_DB_NAME)
        if os.path.exists(db_path):
            if hasattr(self, 'db'):
                self.db.close()
            os.remove(db_path)
        self.db = peewee.SqliteDatabase(db_path)
        self.db.connect()

    @property
    def project_dir(self):
        return os.path.join(self.dirpath, self.PROJECT_DIR_NAME)

    @classmethod
    def get_config(cls):
        cfg = Config()
        cfg.update({
            cfg.BASE_SECTION: {
                cfg.MIGRATOR_DB_URL: 'sqlite:///{}'.format(os.path.join(cls.dirpath, cls.TEST_DB_NAME)),
                cfg.MIGRATOR_DB_TYPE: 'sqlite',
                cfg.MIGRATOR_PROJECT_DIR: os.path.join(cls.dirpath, cls.PROJECT_DIR_NAME),
                cfg.MIGRATOR_MIGRATIONS_DIR: os.path.join(cls.dirpath, cls.MIGRATIONS_DIR_NAME),
                cfg.MIGRATOR_MODELS_PATH: '{}.{}'.format(cls.PROJECT_DIR_NAME, cls.MODELS_FILE_NAME),
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

