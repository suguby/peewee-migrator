# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import sys
from inspect import getmodule, ismethod, isclass

from peewee import BaseModel, ForeignKeyField
from playhouse.reflection import Introspector

if sys.version_info > (3,):
    if sys.version_info > (3, 4):
        from importlib import reload
    else:
        from imp import reload

__all__ = ['Inspector']


class Inspector(object):
    EXCLUDED_FIELDS = {
        'c', 'choices', 'help_text', 'model_class', 'verbose_name', 'related_name', 'coerce', 'db_column',
        'name', 'db_field', 'deferred'
    }
    NOT_INCLUDE_IF_NULL = {'sequence', 'default', 'constraints', 'schema', 'on_delete', 'on_update', 'extra'}
    NOT_INCLUDE_IF_FALSE = {'primary_key'}
    models_path = ('app.models',)

    def __init__(self, models_path=None, excluded_models=None):
        if models_path is not None:
            self.models_path = models_path
        self.excluded_models = [] if excluded_models is None else excluded_models

    @staticmethod
    def is_model(obj):
        return isclass(obj) and (issubclass(obj, BaseModel) or isinstance(obj, BaseModel))

    def get_models(self):
        for path in self.models_path:
            models = reload(__import__(path, fromlist=['*']))
            for model in dir(models):
                if model[0].isupper() and model[0] != '_':
                    obj = getattr(models, model)
                    if self.is_model(obj) and model not in self.excluded_models:
                        yield model, obj

    def get_database_models(self, db=None):
        i = Introspector.from_database(db)
        return i.generate_models().values()

    def inspect_models(self):
        for model, model_obj in self.get_models():
            yield self.inspect_model(model_obj, model=model)

    def inspect_database(self, db):
        models = self.get_database_models(db)
        for model_obj in models:
            yield self.inspect_model(model_obj)

    def inspect_model(self, model_obj, model=None):
        if model is None:
            model = model_obj.__name__
        fields = list(self.collect_fields(model_obj._meta.sorted_fields, model=model))
        return model, model_obj._meta.db_table, fields

    def collect_fields(self, sorted_fields, model=''):
        for field in sorted_fields:
            name = field.name
            field_path = field.__class__.__name__
            field_module = getmodule(field.__class__)
            if field_module is not None:
                field_module = field_module.__name__
                field_path = '{}.{}'.format(field_module, field_path)

            field_params = {
                'index': field.index, 'unique': field.unique, 'null': field.null,
                'initial_kwargs': {}
            }

            for param in dir(field):
                if param[0] == '_' or param in field_params or param in self.EXCLUDED_FIELDS:
                    continue
                try:
                    param_obj = getattr(field, param)
                except:
                    param_obj = None
                if ismethod(param_obj) or (param_obj is None and param in self.NOT_INCLUDE_IF_NULL):
                    continue
                if param_obj is False and param in self.NOT_INCLUDE_IF_FALSE:
                    continue

                field_params['initial_kwargs'][param] = param_obj
            # if field.name != field.db_column:
            #     field_params['initial_kwargs']['db_field'] = field.db_column

            db_column = field.db_column

            if isinstance(field, ForeignKeyField):
                # Сохраняем только название модели
                field_params['initial_kwargs']['rel_model'] = field.rel_model.__name__
                # Нормализация обращения к полю
                db_column = field.name if field.db_column == '{}_id'.format(field.name) else field.db_column
                to_field = {
                    'name': field.to_field.name, 'column': field.to_field.db_column
                }
                if to_field['name'] == 'id' and to_field['column'] == 'id':
                    field_params['initial_kwargs'].pop('to_field', None)
                else:
                    field_params['initial_kwargs']['to_field'] = to_field
                    # Убираем умолчательное значение related_name
                    # model_set = u'{}_set'.format(re.sub('[^\w]+', '_', model.lower()))
                    # if field_params['initial_kwargs']['related_name'] == model_set:
                    #     del field_params['initial_kwargs']['related_name']

            if not field_params['initial_kwargs']:
                field_params.pop('initial_kwargs', None)

            yield {'name': name, 'column': db_column, 'path': field_path, 'params': field_params}
