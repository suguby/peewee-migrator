# -*- coding: utf-8 -*-
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from playhouse.db_url import connect

from migrator.config import Config

if sys.version_info > (3,):
    from configparser import ConfigParser as SafeConfigParser
else:
    from ConfigParser import SafeConfigParser


class TestCliBase(unittest.TestCase):
    MIGRATIONS_DIR_NAME = 'migration'
    TEST_DB_NAME = 'empty.db'
    MODELS_FILE_NAME = 'setup_module_in_successor!!!'
    DB_TYPE = 'sqlite'
    database_config_exists = True

    def setUp(self):
        project_dir = os.path.join(os.path.dirname(__file__), 'apps')

        self.dirpath = tempfile.mkdtemp()
        self.migrations_dir = os.path.join(self.dirpath, self.MIGRATIONS_DIR_NAME)
        os.mkdir(self.migrations_dir)

        cfg = Config()
        cfg.update({
            cfg.BASE_SECTION: {
                cfg.MIGRATOR_DB_URL: '',
                cfg.MIGRATOR_DB_TYPE: self.DB_TYPE,
                cfg.MIGRATOR_PROJECT_DIR: project_dir,
                cfg.MIGRATOR_MIGRATIONS_DIR: self.migrations_dir,
                cfg.MIGRATOR_MODELS_PATH: self.MODELS_FILE_NAME,
                cfg.MIGRATOR_EXCLUDED_MODELS: '',
            }
        })

        db_url = self._get_db_url()
        if db_url:
            self.db = connect(db_url)
            self._clear_db()
            cfg[cfg.BASE_SECTION][cfg.MIGRATOR_DB_URL] = db_url
        else:
            self.database_config_exists = False

        self.config_path = os.path.join(self.dirpath, 'migrator.cfg')
        cfg.save(self.config_path)

    def _get_db_url(self):
        db_path = os.path.join(self.dirpath, self.TEST_DB_NAME)
        db_url = 'sqlite:///{}'.format(db_path)
        return db_url

    def _clear_db(self):
        for table in self.db.get_tables():
            self.db.execute_sql('DROP TABLE {}'.format(table))

    def tearDown(self):
        shutil.rmtree(self.dirpath)

    def _get_migration_revision(self):
        rev = None
        for root, dirs, files in os.walk(self.migrations_dir):
            for file in files:
                if file.startswith('migration'):
                    _, rev = file.split('_')
                    rev = rev[:rev.index('.')]
                    break
        self.assertIsNotNone(rev, 'Cant find migration file!')
        return rev

    def _popen_cli(self, *args):
        popen_start_cmd = [sys.executable, '-m', 'migrator.cli',
                           '--config={}'.format(self.config_path), ] + list(args)
        print(' '.join(popen_start_cmd))
        return subprocess.Popen(popen_start_cmd)


class PostrgesTestMixin(object):
    DB_TYPE = 'postgres'

    def _get_db_url(self):
        cp = SafeConfigParser()
        db_config_path = os.path.join(os.path.dirname(__file__), 'databases.cfg')
        if not os.path.exists(db_config_path):
            return None
        cp.read(db_config_path)
        if not cp.has_option(self.DB_TYPE, 'db_url'):
            return None
        self.database_config_exists = True
        db_url = cp.get(self.DB_TYPE, 'db_url')
        return db_url


class MysqlTestMixin(PostrgesTestMixin):
    DB_TYPE = 'mysql'
