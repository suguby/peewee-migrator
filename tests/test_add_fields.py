# -*- coding: utf-8 -*-
from __future__ import print_function

from tests.utils import TestCliBase, PostrgesTestMixin, MysqlTestMixin


class AddFieldsTest(TestCliBase):
    MODELS_FILE_NAME = 'add_fields.models'

    def test_add_fields(self):
        if not self.database_config_exists:
            self.skipTest('No {} config'.format(self.DB_TYPE))
            return
        from tests.apps.add_fields.source_models import SourceTable
        SourceTable._meta.database = self.db
        SourceTable.create_table()

        process = self._popen_cli('make', '--name', 'test_add')
        process.communicate()
        rev = self._get_migration_revision()
        process = self._popen_cli('apply', rev)
        process.communicate()

        from tests.apps.add_fields.models import SourceTable
        SourceTable._meta.database = self.db
        self.assertEqual(SourceTable.table_exists(), True)


class AddFieldsPostrgesTest(PostrgesTestMixin, AddFieldsTest):
    pass


class AddFieldsMysqlTest(MysqlTestMixin, AddFieldsTest):
    pass
