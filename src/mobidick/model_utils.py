# -*- coding: utf-8 -*-
# Copyright 2017 Mobicage NV
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
# @@license_version:1.2@@

import sys

import yaml
from google.appengine.ext import db

from mcfw.consts import MISSING
from mcfw.rpc import returns, arguments

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


@returns(db.Property)
def add_meta(prop, **kwargs):
    if not isinstance(prop, db.Property):
        raise Exception('Invalid property type %s' % prop)
    for k, v in kwargs.iteritems():
        setattr(prop, '_%s' % k, v)
    return prop


@returns(object)
@arguments(prop=db.Property, meta=unicode, default=object)
def get_meta(prop, meta, default=MISSING):
    if default is MISSING:
        return getattr(prop, '_%s' % meta)
    else:
        return getattr(prop, '_%s' % meta, default)


@returns(dict)
@arguments(old_model=db.Model)
def copy_model_properties(old_model):
    kwargs = dict()
    for propname, propvalue in old_model.properties().iteritems():
        if propname == "_class":
            continue
        if isinstance(propvalue, db.ReferenceProperty):
            value = getattr(old_model.__class__, propname).get_value_for_datastore(old_model)  # the key
        else:
            value = getattr(old_model, propname)
        kwargs[propname] = value

    if isinstance(old_model, db.Expando):
        for dynamic_propname in old_model.dynamic_properties():
            kwargs[dynamic_propname] = getattr(old_model, dynamic_propname)

    return kwargs


@returns(unicode)
@arguments(model=db.Model)
def model_to_yaml(model):
    def _write_value(stream, value):
        if value is None:
            value = 'null'
        elif isinstance(value, basestring):
            if value == '' or value.isdigit():
                # put empty or numeric strings between single quotes
                value = "'%s'" % value
            elif value.find('\n') != -1:
                value = "|\n  %s" % ("\n  ".join(value.splitlines()))
        stream.write(str(value))

    def _write_doc(stream, propobject, indent=0):
        doc = get_meta(propobject, 'doc', None)
        if doc:
            for i, l in enumerate(doc.splitlines()):
                if i:
                    stream.write('\n%s' % (indent * ' ',))
                stream.write("  # %s" % l)

    stream = StringIO()
    prev_prefix = None

    def sort_prop(item):
        propname, propobject = item
        return get_meta(propobject, 'order', default=sys.maxint), propname

    for propname, propobject in sorted(model.properties().items(), key=sort_prop):
        if propname == "_class":
            continue

        # Grouping settings with the same prefix
        if prev_prefix and not propname.startswith(prev_prefix):
            stream.write('\n')
        prev_prefix = ''
        for c in propname:
            if c.islower():
                prev_prefix += c
            else:
                break

        # Write doc strings
        doc = getattr(propobject, '_doc', None)
        if doc:
            for l in doc.splitlines():
                stream.write("# %s\n" % l)

        # Write property name and value
        stream.write(propname)
        stream.write(":")
        if isinstance(propobject, db.ListProperty):
            l = getattr(model, propname)
            if l:
                for value in l:
                    stream.write("\n- ")
                    _write_value(stream, value)
            else:
                stream.write(" []")
        else:
            stream.write(" ")
            _write_value(stream, getattr(model, propname))

        stream.write("\n")

    return stream.getvalue()


@returns(db.Model)
@arguments(model=db.Model, stream=unicode)
def populate_model_by_yaml(model, stream):
    d = yaml.load(stream)
    if not d:
        raise Exception("Empty yaml")
    missing_properties = [propname for propname in model.properties() if propname not in d]
    if missing_properties:
        raise Exception("Missing properties: %s" % ", ".join(missing_properties))

    for propname, propobject in model.properties().iteritems():
        value = d[propname]
        if value is not None and isinstance(propobject, db.StringProperty):
            value = str(value)
        setattr(model, propname, value)
    return model
