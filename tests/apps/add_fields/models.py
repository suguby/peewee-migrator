# -*- coding: utf-8 -*-
import peewee

from tests.apps.add_fields.source_models import SourceTable as OldTable


# добавим поля к исходной таблице
class SourceTable(OldTable):
    #  TODO тестировать разные параметры полей
    float_field_2 = peewee.FloatField(null=True)
    int_field_2 = peewee.IntegerField(null=True)
    char_field_2 = peewee.CharField(max_length=128, null=True)
    text_field_2 = peewee.TextField(null=True)
    boolean_field_2 = peewee.BooleanField(null=True)
