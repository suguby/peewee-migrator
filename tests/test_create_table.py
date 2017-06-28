# -*- coding: utf-8 -*-
from __future__ import print_function

from tests.utils import TestCliBase, PostrgesTestMixin, MysqlTestMixin


class CreateTableTest(TestCliBase):
    MODELS_FILE_NAME = 'create_table.models'

    def test_create_table(self):
        if not self.database_config_exists:
            self.skipTest('No {} config'.format(self.DB_TYPE))
            return
        process = self._popen_cli('make', '--name', 'test_empty')
        process.communicate()
        rev = self._get_migration_revision()
        from tests.apps.create_table.models import CreateTestDbTable
        CreateTestDbTable._meta.database = self.db

        process = self._popen_cli('apply', rev)
        process.communicate()
        self.assertEqual(CreateTestDbTable.table_exists(), True)

        process = self._popen_cli('revert', rev)
        process.communicate()
        self.assertEqual(CreateTestDbTable.table_exists(), False)


class CreateTablePostrgesTest(PostrgesTestMixin, CreateTableTest):
    pass


class CreateTableMysqlTest(MysqlTestMixin, CreateTableTest):
    pass
