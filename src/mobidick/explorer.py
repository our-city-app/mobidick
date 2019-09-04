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

import inspect
import json
import logging
import new
import os
import time
import traceback

from google.appengine.api import xmpp, users
from google.appengine.ext import deferred
from google.appengine.ext.webapp import template
from mobidick.models import Code
import webapp2
from mobidick.business import get_templates_dir


class CodeTO(object):
    # id = long_property('1')
    # timestamp = long_property('2')
    # author = unicode_property('3')
    # name = unicode_property('4')
    # source = unicode_property('5')
    # functions = unicode_list_property('6')
    # version = long_property('7')

    id = None
    timestamp = None
    author = None
    name = None
    source = None
    functions = None
    version = None

    @staticmethod
    def fromDBCode(code):
        ct = CodeTO()
        ct.id = code.key().id()
        ct.timestamp = code.timestamp
        ct.author = unicode(code.author.email()) if code.author else u'unknown@mobicage.com'
        ct.name = code.name
        ct.source = code.source
        ct.functions = code.functions
        ct.version = code.version
        return ct

class RunResultTO(object):
    # result = unicode_property('1')
    # succeeded = bool_property('2')
    # time = long_property('3')

    result = None
    succeeded = None
    time = None

def now():
    return int(time.time())

# @rest('/mobiadmin/rest/explore/code/compile', 'post')
# @returns(CodeTO)
# @arguments(source=unicode, name=str)
class CompileRequestHandler(webapp2.RequestHandler):

    def post(self):
        source = self.request.get('source')
        name = self.request.get('name')
        user = users.get_current_user()
        m = new.module(str(name))
        exec source in m.__dict__
        functions = inspect.getmembers(m, lambda x: inspect.isfunction(x) and x.__module__ == m.__name__)
        code = Code().all().filter("name =", name).get()
        if not code:
            code = Code()
        code.author = user
        code.timestamp = now()
        code.name = name
        code.source = source
        code.functions = [unicode(f[0]) for f in functions]
        code.version = code.version + 1 if code.version else 1
        code.put()
        self.response.headers['Content-Type'] = 'application/json'
        json.dump(CodeTO.fromDBCode(code).__dict__, self.response.out)
        return

# @rest('/mobiadmin/rest/explore/code/get', 'get')
# @returns([CodeTO])
# @arguments()
class GetCodeRequestHandler(webapp2.RequestHandler):

    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        json.dump([CodeTO.fromDBCode(code).__dict__ for code in Code.all()], self.response.out)
        return

# @rest('/mobiadmin/rest/explore/code/delete', 'post')
# @returns(NoneType)
# @arguments(id=int)
class DeleteCodeRequestHandler(webapp2.RequestHandler):

    def post(self):
        id_ = int(self.request.get('id'))
        Code.get_by_id(id_).delete()
        return

# @rest('/mobiadmin/rest/explore/code/run', 'post')
# @returns(RunResultTO)
# @arguments(codeid=int, version=int, function=unicode, in_a_deferred=bool)
class RunCodeRequestHandler(webapp2.RequestHandler):

    def post(self):
        codeid = int(self.request.get('codeid'))
        version = int(self.request.get('version'))
        function = self.request.get('function')
        in_a_deferred = (self.request.get('in_a_deferred', False).lower() == 'true')
        if in_a_deferred:
            deferred.defer(_run_deferred, codeid, version, function)
            return None
        code = Code.get_by_id(codeid)
        m = new.module(str(code.name))
        exec code.source in m.__dict__
        f = getattr(m, function)
        start = time.time()
        try:
            r = f()
            runtime = time.time() - start
            rr = RunResultTO()
            rr.result = unicode(r)
            rr.succeeded = True
            rr.time = int(runtime)
        except:
            runtime = time.time() - start
            rr = RunResultTO()
            rr.result = unicode(traceback.format_exc())
            rr.succeeded = False
            rr.time = int(runtime)
            logging.exception("Code execution failed")
        self.response.headers['Content-Type'] = 'application/json'
        json.dump(rr.__dict__, self.response.out)
        return

class ExplorerPage(webapp2.RequestHandler):

    def get(self):
        user = users.get_current_user()
        path = os.path.join(get_templates_dir(), 'explorer.html')
        self.response.out.write(template.render(path, {
            'debug':False,
            'user':user,
            'session':"/"}))

def _run_deferred(codeid, version, function):
    code = Code.get_by_id(codeid)
    m = new.module(str(code.name))
    exec code.source in m.__dict__
    f = getattr(m, function)
    start = time.time()
    try:
        r = f()
        runtime = time.time() - start
        rr = dict(result=unicode(r), succeeded=True, time=int(runtime))
    except:
        runtime = time.time() - start
        rr = dict(result=unicode(traceback.format_exc()), succeeded=False, time=int(runtime))
    xmpp.send_message("g.audenaert@gmail.com", json.dumps(rr))
