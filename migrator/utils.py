# -*- coding: utf-8 -*-
import base64
import json
import pickle


class SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return super(SafeEncoder, self).default(self, obj)
        except TypeError:
            try:
                if isinstance(obj, memoryview):
                    obj = bytes(obj)
                return {'__pickled_object__': base64.b64encode(pickle.dumps(obj)).decode()}
            except:
                return '__unencoded_object__'


def pickle_hook(dct):
    if '__pickled_object__' in dct:
        try:
            return pickle.loads(base64.b64decode(dct['__pickled_object__']))
        except:
            return '__unencoded_object__'
    return dct