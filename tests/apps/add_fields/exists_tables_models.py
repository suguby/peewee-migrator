# -*- coding: utf-8 -*-
import peewee


class AddFieldsTestDbTable(peewee.Model):
    float_field = peewee.FloatField()
    int_field = peewee.IntegerField()
    char_field = peewee.CharField(max_length=64)
    text_field = peewee.TextField()
    boolean_field = peewee.BooleanField()
