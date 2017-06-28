# -*- coding: utf-8 -*-
from __future__ import print_function

import peewee

from tests.utils import TestCliBase, PostrgesTestMixin, MysqlTestMixin


class AddFieldsTest(TestCliBase):
    MODELS_FILE_NAME = 'add_fields.models'

    def test_add_fields(self):
        if not self.database_config_exists:
            self.skipTest('No {} config'.format(self.DB_TYPE))
            return
        from tests.apps.add_fields.exists_tables_models import AddFieldsTestDbTable as ExistTable
        ExistTable._meta.database = self.db
        with self.db.atomic():
            ExistTable.create_table()

        process = self._popen_cli('make', '--name', 'test_add')
        process.communicate()
        rev = self._get_migration_revision()

        process = self._popen_cli('apply', rev)
        process.communicate()
        from tests.apps.add_fields.models import AddFieldsTestDbTable
        AddFieldsTestDbTable._meta.database = self.db
        self.assertEqual(AddFieldsTestDbTable.table_exists(), True)
        obj1 = AddFieldsTestDbTable(
            float_field=3.1415,
            int_field=42,
            char_field='hello',
            text_field='world',
            boolean_field=True,

            float_field_2=2.7182,
            int_field_2=24,
            char_field_2='preved',
            text_field_2='medved',
            boolean_field_2=False,
        )
        with self.db.atomic():
            obj1.save()

        process = self._popen_cli('revert', rev)
        process.communicate()
        self.assertEqual(AddFieldsTestDbTable.table_exists(), True)
        obj2 = AddFieldsTestDbTable(
            float_field=3.1415,
            int_field=42,
            char_field='hello',
            text_field='world',
            boolean_field=True,

            float_field_2=2.7182,
            int_field_2=24,
            char_field_2='preved',
            text_field_2='medved',
            boolean_field_2=False,
        )
        try:
            with self.db.atomic():
                obj2.save()
        except (peewee.OperationalError, peewee.ProgrammingError):
            # TODO конкретизировать ошибку - вдруг не "колонки не существует" ???
            pass
        else:
            self.fail("Backward migration didn't drop columns")


class AddFieldsPostrgesTest(PostrgesTestMixin, AddFieldsTest):
    pass


class AddFieldsMysqlTest(MysqlTestMixin, AddFieldsTest):
    pass
