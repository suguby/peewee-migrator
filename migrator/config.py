# -*- coding: utf-8 -*-
import codecs

import sys


if sys.version_info > (3,):
    from configparser import ConfigParser as SafeConfigParser
    from io import StringIO
else:
    from ConfigParser import SafeConfigParser
    from StringIO import StringIO

from playhouse.db_url import connect

__all__ = ['Config']


class Config(dict):
    BASE_SECTION = 'migrator'
    MIGRATOR_DB_URL = 'db_url'
    MIGRATOR_DB_TYPE = 'db_type'
    MIGRATOR_PROJECT_DIR = 'project_dir'
    MIGRATOR_MIGRATIONS_DIR = 'migrations_dir'

    # Список через запятую
    MIGRATOR_MODELS_PATH = 'models_path'
    MIGRATOR_EXCLUDED_MODELS = 'excluded_models'

    def __init__(self, *args, **kwargs):
        self.cp = SafeConfigParser()
        super(Config, self).__init__(*args, **kwargs)

    def make_default(self):
        self.clear()
        self.update({
            self.BASE_SECTION: {
                self.MIGRATOR_DB_URL: 'sqlite:///sqlite.db',
                self.MIGRATOR_DB_TYPE: 'sqlite',
                self.MIGRATOR_PROJECT_DIR: 'project',
                self.MIGRATOR_MIGRATIONS_DIR: 'migrations',
                self.MIGRATOR_MODELS_PATH: 'app.models',
                self.MIGRATOR_EXCLUDED_MODELS: ''
            }
        })
        self.save_to_cp()

    def load(self, file_path):
        self.cp = SafeConfigParser()
        self.cp.read(file_path)
        self.load_from_cp()

    def load_from_cp(self):
        for section in self.cp.sections():
            for option in self.cp.options(section):
                value = self.cp.get(section, option)
                self.setdefault(section, {})[option] = value

    def save(self, file_path):
        self.save_to_cp()
        self.cp.write(codecs.open(file_path, 'w', 'utf-8'))

    def to_string_io(self):
        string = StringIO()
        self.save_to_cp()
        self.cp.write(string)
        return string

    def save_to_cp(self):
        self.cp = SafeConfigParser()
        for section, variables in self.items():
            self.cp.add_section(section)
            for name, value in variables.items():
                self.cp.set(section, name, value)

    def get_db(self):
        url = self.get(self.BASE_SECTION, {}).get(self.MIGRATOR_DB_URL, None)
        if url is None:
            return None
        return connect(url)

    def get_setting(self, key, default=None):
        return self.get(self.BASE_SECTION, {}).get(key, default)

    def _get_list_by_comma(self, value):
        return [x.strip() for x in value.split(',')]

    def get_excluded(self):
        return self._get_list_by_comma(self.get_setting(self.MIGRATOR_EXCLUDED_MODELS, ''))

    def get_models_paths(self):
        return self._get_list_by_comma(self.get_setting(self.MIGRATOR_MODELS_PATH))