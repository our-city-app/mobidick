# -*- coding: utf-8 -*-
# Copyright 2016 Mobicage NV
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
# @@license_version:1.1@@

import inspect
import json
import threading
from types import NoneType

import webapp2

from mcfw.consts import AUTHENTICATED, NOT_AUTHENTICATED
from mcfw.rpc import run, parse_parameters

_exposed = dict()
_precall_hooks = list()
_postcall_hooks = list()

class InjectedFunctions(object):

    def __init__(self):
        self._get_session_function = None

    @property
    def get_current_session(self):
        return self._get_session_function

    @get_current_session.setter
    def get_current_session(self, function):
        self._get_session_function = function

INJECTED_FUNCTIONS = InjectedFunctions()
del InjectedFunctions

def register_precall_hook(callable_):
    _precall_hooks.append(callable_)

def register_postcall_hook(callable_):
    _postcall_hooks.append(callable_)

def rest(uri, method, authenticated=True, silent=False, silent_result=False, read_only_access=False):
    if not method in ('get', 'post'):
        ValueError('method')

    def wrap(f):
        if not inspect.isfunction(f):
            raise ValueError("f is not of type function!")

        def wrapped(*args, **kwargs):
            return f(*args, **kwargs)

        wrapped.__name__ = f.__name__
        wrapped.meta = {"rest": True, "uri": uri, "method": method, "authenticated": authenticated, "silent": silent, "silent_result": silent_result, "read_only_access": read_only_access}
        if hasattr(f, "meta"):
            wrapped.meta.update(f.meta)
        return wrapped

    return wrap

class ResponseTracker(threading.local):

    def __init__(self):
        self.current_response = None
        self.current_request = None

_current_reponse_tracker = ResponseTracker()
del ResponseTracker

class GenericRESTRequestHandler(webapp2.RequestHandler):

    @staticmethod
    def getCurrentResponse():
        return _current_reponse_tracker.current_response

    @staticmethod
    def getCurrentRequest():
        return _current_reponse_tracker.current_request

    @staticmethod
    def clearCurrent():
        _current_reponse_tracker.current_response = None

    @staticmethod
    def setCurrent(request, response):
        _current_reponse_tracker.current_request = request
        _current_reponse_tracker.current_response = response

    def ctype(self, type_, value):
        if not isinstance(type_, (list, tuple)):
            if type_ == bool:
                return bool(value) and value.lower() == "true"
            return type_(value)
        elif isinstance(type_, list):
            return [self.ctype(type_[0], item) for item in value.split(',')]
        elif type_ == (str, unicode):
            return unicode(value)
        elif type_ == (int, long):
            return long(value)
        elif type_ == (int, long, NoneType):
            return None if value is None or value == "" else long(value)
        raise NotImplementedError()

    def get(self):
        GenericRESTRequestHandler.setCurrent(self.request, self.response)
        key = self.request.path, "get"
        if not key in _exposed:
            self.response.set_status(404, "Call not found!")
            return
        f = _exposed[key]
        kwargs = dict(((name, self.ctype(type_, self.request.GET[name])) for name, type_ in f.meta["kwarg_types"].iteritems() if name in self.request.GET))
        result = self.run(f, kwargs, kwargs)
        self.response.headers['Content-Type'] = 'text/json'
        self.response.out.write(json.dumps(result))

    def post(self):
        GenericRESTRequestHandler.setCurrent(self.request, self.response)
        key = self.request.path, "post"
        if not key in _exposed:
            self.response.set_status(404, "Call not found!")
            return
        f = _exposed[(self.request.path, "post")]
        if self.request.headers.get('Content-Type', "").startswith('application/json-rpc'):
            parameters = json.loads(self.request.body)
        else:
            parameters = json.loads(self.request.POST['data'])
        kwargs = parse_parameters(f, parameters)
        result = self.run(f, parameters, kwargs)
        self.response.headers['Content-Type'] = 'text/json'
        self.response.out.write(json.dumps(result))

    def run(self, f, parameters, kwargs):
        if f.meta["authorized_function"]:
            if not f.meta["authorized_function"]():
                self.abort(401)
                return
        if f.meta["authenticated"]:
            session = INJECTED_FUNCTIONS.get_current_session()
            if session and  session.read_only and not f.meta["read_only_access"]:
                self.abort(401)
                return
        for hook in _precall_hooks:
            hook(f, parameters)
        try:
            result = run(f, kwargs)
        except Exception, e:
            for hook in _postcall_hooks:
                hook(f, False, kwargs, e)
            raise
        for hook in _postcall_hooks:
            hook(f, True, kwargs, result)
        return result


def rest_functions(module, authentication=AUTHENTICATED, authorized_function=None):
    if not authentication in (AUTHENTICATED, NOT_AUTHENTICATED):
        raise ValueError()
    for f in (function for (name, function) in inspect.getmembers(module, lambda x: inspect.isfunction(x))):
        if hasattr(f, 'meta') and "rest" in f.meta and f.meta["rest"]:
            if (authentication == AUTHENTICATED and f.meta["authenticated"]) \
                or (authentication == NOT_AUTHENTICATED and not f.meta["authenticated"]):
                meta_uri = f.meta["uri"]
                meta_method = f.meta["method"]
                f.meta["authorized_function"] = authorized_function
                for uri in (meta_uri if isinstance(meta_uri, (list, tuple)) else (meta_uri,)):
                    _exposed[(uri, meta_method)] = f
                    yield uri, GenericRESTRequestHandler
