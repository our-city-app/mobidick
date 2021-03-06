# -*- coding: utf-8 -*-
# Copyright 2019 Green Valley Belgium NV
# NOTICE: THIS FILE HAS BEEN MODIFIED BY GREEN VALLEY BELGIUM NV IN ACCORDANCE WITH THE APACHE LICENSE VERSION 2.0
# Copyright 2018 GIG Technology NV
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# @@license_version:1.6@@

from cStringIO import StringIO
import datetime
from functools import wraps
from struct import Struct
import time
import types

try:
    from google.appengine.api import users
    from google.appengine.ext import db
except ImportError:  # Allow running outside google app engine
    pass

try:
    import cPickle as pickle
except ImportError:
    import pickle

_serializers = dict()
_ushortStruct = Struct("<H")
_intStruct = Struct("<i")
_longStruct = Struct("<q")
_longLongStruct = Struct("<q")
_doubleStruct = Struct("<d")

class CustomProperty(object):
    pass

def register(type_, serializer, deserializer):
    _serializers[type_] = (serializer, deserializer)

def serialize(type_, obj):
    stream = StringIO()
    _serializers[type_][0](stream, obj)
    return stream.getvalue()

def deserialize(type_, stream):
    if isinstance(stream, (str, unicode)):
        stream = StringIO(stream)
    if isinstance(stream, db.Blob):
        stream = StringIO(str(stream))
    return _serializers[type_][1](stream)

def get_serializer(type_):
    return _serializers[type_][0]

def get_deserializer(type_):
    return _serializers[type_][1]

def serializer(f):

    @wraps(f)
    def wrapped(stream, obj, *args, **kwargs):
        if obj is None:
            stream.write('0')
        else:
            stream.write('1')
            f(stream, obj, *args, **kwargs)

    return wrapped

def deserializer(f):

    @wraps(f)
    def wrapped(stream, *args, **kwargs):
        if stream.read(1) == '0':
            return None
        else:
            return f(stream, *args, **kwargs)

    return wrapped

@serializer
def s_str(stream, obj):
    stream.write(_intStruct.pack(len(obj)))
    stream.write(obj)

@deserializer
def ds_str(stream):
    (size,) = _intStruct.unpack(stream.read(_intStruct.size))
    return stream.read(size)

register(str, s_str, ds_str)

@serializer
def s_unicode(stream, obj):
    s_str(stream, obj.encode("UTF-8"))

@deserializer
def ds_unicode(stream):
    s = ds_str(stream)
    return None if s is None else s.decode("UTF-8")

register(unicode, s_unicode, ds_unicode)

@serializer
def s_bool(stream, obj):
    stream.write('1' if obj else '0')

@deserializer
def ds_bool(stream):
    return stream.read(1) == '1'

register(bool, s_bool, ds_bool)

@serializer
def s_ushort(stream, obj):
    stream.write(_ushortStruct.pack(obj))

@deserializer
def ds_ushort(stream):
    (value,) = _ushortStruct.unpack(stream.read(_ushortStruct.size))
    return value

@serializer
def s_long(stream, obj):
    stream.write(_longStruct.pack(obj))

@deserializer
def ds_long(stream):
    (value,) = _longStruct.unpack(stream.read(_longStruct.size))
    return value

register(int, s_long, ds_long)

@serializer
def s_long_long(stream, obj):
    stream.write(_longLongStruct.pack(obj))

@deserializer
def ds_long_long(stream):
    (value,) = _longLongStruct.unpack(stream.read(_longLongStruct.size))
    return value

register(long, s_long_long, ds_long_long)

@serializer
def s_float(stream, obj):
    stream.write(_doubleStruct.pack(obj))

@deserializer
def ds_float(stream):
    (value,) = _doubleStruct.unpack(stream.read(_doubleStruct.size))
    return value

register(float, s_float, ds_float)

@serializer
def s_datetime(stream, obj):
    s_long(stream, int(time.mktime(obj.timetuple())))

@deserializer
def ds_datetime(stream):
    return datetime.datetime.fromtimestamp(ds_long(stream))

register(datetime.datetime, s_datetime, ds_datetime)

@serializer
def s_key(stream, obj):
    s_str(stream, str(obj))

@deserializer
def ds_key(stream):
    return db.Key(ds_str(stream))

if 'db' in locals():
    register(db.Key, s_key, ds_key)

@serializer
def s_any(stream, obj):
    pickle.dump(obj, stream)

@deserializer
def ds_any(stream):
    return pickle.load(stream)

@serializer
def s_user(stream, obj):
    s_unicode(stream, obj.email())

@deserializer
def ds_user(stream):
    return users.User(ds_unicode(stream))

if 'users' in locals():
    register(users.User, s_user, ds_user)

def _get_model_properties(model):
    props = model.properties()
    if not hasattr(model, 'MC_ATTRIBUTES_HASH'):
        prop_keys = sorted(props.keys())
        prop_key_hash = hash(','.join(prop_keys))
        model.MC_ATTRIBUTES_HASH = prop_key_hash
        model.MC_ATTRIBUTES = prop_keys
    else:
        prop_keys = model.MC_ATTRIBUTES
        prop_key_hash = model.MC_ATTRIBUTES_HASH
    return prop_key_hash, prop_keys, props

@serializer
def s_model(stream, obj, clazz=None):
    if clazz is None:
        clazz = obj.__class__
    hash_, keys, properties = _get_model_properties(clazz)
    s_long(stream, hash_)
    s_str(stream, str(obj.key()))
    for key in keys:
        prop = properties[key]
        value = getattr(obj, key)
        if prop.__class__ in (db.StringProperty, db.PostalAddressProperty, db.EmailProperty, db.PhoneNumberProperty):
            s_unicode(stream, value)
        elif prop.__class__ in (db.IntegerProperty, db.RatingProperty):
            s_long(stream, value)
        elif prop.__class__ == db.DateTimeProperty:
            s_datetime(stream, value)
        elif prop.__class__ == db.UserProperty:
            s_str(stream, value.email() if value else None)
        elif prop.__class__ == db.BooleanProperty:
            s_bool(stream, value)
        elif prop.__class__ == db.TextProperty:
            s_unicode(stream, value)
        elif prop.__class__ == db.StringListProperty:
            s_long(stream, len(value))
            for s in value:
                s_unicode(stream, s)
        elif prop.__class__ == db.ListProperty and prop.item_type == bool:
            s_long(stream, len(value))
            for b in value:
                s_bool(stream, b)
        elif prop.__class__ == db.ListProperty and (prop.item_type == int or prop.item_type == long):
            s_long(stream, len(value))
            for i in value:
                s_long(stream, i)
        elif prop.__class__ == db.ListProperty and prop.item_type == users.User:
            s_long(stream, len(value))
            for u in value:
                s_user(stream, u)
        elif isinstance(prop, CustomProperty):
            prop.get_serializer()(stream, value)
        elif prop.__class__ == db.polymodel._ClassKeyProperty:
            continue
        else:
            raise NotImplementedError("Can not serialize %s instances" % prop.__class__)

@deserializer
def ds_model(stream, cls):
    return model_deserializer(stream, cls)

def model_deserializer(stream, cls):
    hash_, keys, properties = _get_model_properties(cls)
    inst_hash = ds_long(stream)
    if hash_ != inst_hash:
        raise SerializedObjectOutOfDateException()
    kwargs = dict()
    model_key = ds_str(stream)
    for property_name in keys:
        prop = properties[property_name]
        if prop.__class__ in (db.StringProperty, db.PostalAddressProperty, db.EmailProperty, db.PhoneNumberProperty):
            value = ds_unicode(stream)
        elif prop.__class__ in (db.IntegerProperty, db.RatingProperty):
            value = ds_long(stream)
        elif prop.__class__ == db.DateTimeProperty:
            value = ds_datetime(stream)
        elif prop.__class__ == db.UserProperty:
            value = ds_str(stream)
            if value:
                value = users.User(value)
        elif prop.__class__ == db.BooleanProperty:
            value = ds_bool(stream)
        elif prop.__class__ == db.TextProperty:
            value = ds_unicode(stream)
        elif prop.__class__ == db.StringListProperty:
            length = ds_long(stream)
            value = [ ds_unicode(stream) for _ in xrange(length) ]
        elif prop.__class__ == db.ListProperty and prop.item_type == bool:
            length = ds_long(stream)
            value = [ ds_bool(stream) for _ in xrange(length) ]
        elif prop.__class__ == db.ListProperty and (prop.item_type == int or prop.item_type == long):
            length = ds_long(stream)
            value = [ ds_long(stream) for _ in xrange(length) ]
        elif prop.__class__ == db.ListProperty and prop.item_type == users.User:
            length = ds_long(stream)
            value = [ ds_user(stream) for _ in xrange(length) ]
        elif isinstance(prop, CustomProperty):
            value = prop.get_deserializer()(stream)
        elif prop.__class__ == db.polymodel._ClassKeyProperty:
            continue
        else:
            raise NotImplementedError("Can not deserialize %s instances" % prop.__class__)
        kwargs[property_name] = value

    return cls(key=db.Key(model_key), **kwargs)

def get_list_serializer(func):
    @serializer
    def s_list(stream, obj):
        if isinstance(obj, types.GeneratorType):
            obj = list(obj)
        stream.write(_intStruct.pack(len(obj)))
        for o in obj:
            func(stream, o)
    return s_list

def get_list_deserializer(func, needsVersionArg=False):
    if needsVersionArg:
        @deserializer
        def ds_list_version(stream, version):
            (size,) = _intStruct.unpack(stream.read(_intStruct.size))
            return [func(stream, version) for _ in xrange(size)]
        return ds_list_version
    else:
        @deserializer
        def ds_list(stream):
            (size,) = _intStruct.unpack(stream.read(_intStruct.size))
            return [func(stream) for _ in xrange(size)]
        return ds_list

class List(object):

    def __init__(self, type_):
        self.type = type_

    def __hash__(self):
        return hash("List") + hash(self.type)

    def __eq__(self, other):
        return hash(self) == hash(other)

s_str_list = get_list_serializer(s_str)
ds_str_list = get_list_deserializer(ds_str)
register(List(str), s_str_list, ds_str_list)

s_unicode_list = get_list_serializer(s_unicode)
ds_unicode_list = get_list_deserializer(ds_unicode)
register(List(unicode), s_unicode_list, ds_unicode_list)

s_bool_list = get_list_serializer(s_bool)
ds_bool_list = get_list_deserializer(ds_bool)
register(List(bool), s_bool_list, ds_bool_list)

s_long_list = get_list_serializer(s_long)
ds_long_list = get_list_deserializer(ds_long)
register(List(long), s_long_list, ds_long_list)

s_float_list = get_list_serializer(s_float)
ds_float_list = get_list_deserializer(ds_float)
register(List(float), s_float_list, ds_float_list)

class SerializedObjectOutOfDateException(Exception):
    pass
