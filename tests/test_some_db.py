# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys

from tests.test_create_table import CreateTableTest

if sys.version_info > (3,):
    from configparser import ConfigParser as SafeConfigParser
else:
    from ConfigParser import SafeConfigParser


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


class CreateTablePostrgesTest(PostrgesTestMixin, CreateTableTest):
    pass


# class AddFieldsPostrgesTest(PostrgesTestMixin, AddFieldsTest):
#     pass
