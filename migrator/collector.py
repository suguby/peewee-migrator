# -*- coding: utf-8 -*-


__all__ = ['ChangesCollector']


class ChangesCollector(object):
    @classmethod
    def get_table_matches(cls, new, old):
        matches = {}
        for name, model in new.items():
            match = None
            if name in old:
                match = name
            else:
                for o_name, o_model in old.items():
                    if o_model['table'] == model['table']:
                        match = o_name
            if match is not None:
                matches[name] = match
        return matches

    @classmethod
    def get_columns_to_drop(cls, new_fields, old_fields, new_model, old_model, field_matches):
        fields_to_drop = []
        matched_old_fields = set(field_matches.values())
        for x in old_fields.keys():
            if x in matched_old_fields:
                continue
            fields_to_drop.append((new_model['table'], cls.get_db_field(old_fields[x])))
        return fields_to_drop

    @classmethod
    def get_columns_to_create(cls, new_fields, old_fields, new_model, old_model, field_matches):
        fields_to_create = []
        existed_fields = set(field_matches.keys())
        for x in new_fields.keys():
            if x in existed_fields:
                continue
            fields_to_create.append(
                (new_model['table'], cls.get_db_field(new_fields[x]), '{}.{}'.format(new_model['name'], x))
            )

        return fields_to_create

    @classmethod
    def get_field_matches(cls, new_ordered, new_fields, old_fields):
        field_matches = {}
        for field in new_ordered:
            match = None
            if field['name'] in old_fields:
                match = field['name']
            # else:
            if True:
                for o_field_name, o_field in old_fields.items():
                    if cls.get_db_field(field) == cls.get_db_field(o_field):
                        match = o_field_name
            if match is not None:
                field_matches[field['name']] = match
        return field_matches

    @classmethod
    def get_db_field(cls, field):
        return str(field.get('params', {}).get('db_field', field['name']))

    @classmethod
    def get_field_indexes(cls, new_field, old_field, new_model, old_model):
        indexes_diff = []
        # Обычные индексы
        if new_field.get('index', False):
            if not old_field.get('index', False):
                indexes_diff.append(('add', new_model['table'], cls.get_db_field(new_field), False))
        else:
            if old_field.get('index', False):
                indexes_diff.append(('drop', new_model['table'], cls.get_db_field(new_field)))
        # Уникальные индексы
        if new_field.get('unique', False):
            if not old_field.get('unique', False):
                indexes_diff.append(('add', new_model['table'], cls.get_db_field(new_field), True))
        else:
            if old_field.get('unique', False):
                indexes_diff.append(('drop', new_model['table'], cls.get_db_field(new_field)))
        return indexes_diff

    @classmethod
    def get_field_null(cls, new_field, old_field, new_model, old_model):
        null_diff = []
        if new_field.get('null', False):
            if not old_field.get('null', False):
                null_diff.append(('add', new_model['table'], cls.get_db_field(new_field)))
        else:
            if old_field.get('null', False):
                null_diff.append((new_model['table'], cls.get_db_field(new_field)))
        return null_diff

    @classmethod
    def get_field_rename(cls, new_field, old_field, new_model, old_model):
        # TODO: Обрабатывать переименование полей модели
        return []
