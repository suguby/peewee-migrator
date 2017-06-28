# -*- coding: utf-8 -*-
import peewee


class AddFieldsTestDbTable(peewee.Model):
    # старые поля, см tests/apps/add_fields/exists_tables_models.py
    float_field = peewee.FloatField()
    int_field = peewee.IntegerField()
    char_field = peewee.CharField(max_length=64)
    text_field = peewee.TextField()
    boolean_field = peewee.BooleanField()
    # добавим несколько
    float_field_2 = peewee.FloatField(null=True)
    int_field_2 = peewee.IntegerField(null=True)
    char_field_2 = peewee.CharField(max_length=128, null=True)
    text_field_2 = peewee.TextField(null=True)
    boolean_field_2 = peewee.BooleanField(null=True)
    #  TODO тестировать разные параметры полей
