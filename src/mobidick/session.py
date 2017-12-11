# -*- coding: utf-8 -*-
# Copyright 2017 GIG Technology NV
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
# @@license_version:1.3@@

import json
import uuid

from google.appengine.ext import db
import webapp2

from mobidick.consts import SESSION_TIMEOUT
from mobidick.cookie import set_cookie, parse_cookie
from mobidick.job import run_job
from mobidick.models import Account, Session, get_server_settings
from mobidick.utils import call_rogerthat, now


class CreateSessionRequestHandler(webapp2.RequestHandler):

    def get(self):
        api_key = self.request.get("ak", "")
        sikey = self.request.get("sik", "")

        if not (api_key and sikey):
            self.response.set_status(401)
            return

        _, response = call_rogerthat(api_key, "system.get_info", {}, str(uuid.uuid4()))
        result = json.loads(response)

        if result["error"]:
            self.response.set_status(401, result["error"])
            return
        result = result["result"]

        account = Account.get_by_key_name(result["email"])
        if account and account.locked:
            pass
        elif not account or account.apikey != api_key or account.sikey != sikey:
            account = Account(key_name=result["email"])
            account.apikey = api_key
            account.sikey = sikey
            account.name = result["name"]
            account.avatar = result["avatar"]
            account.locked = False
            account.put()

        secret = unicode(uuid.uuid4()).replace("-", "")
        Session(key_name=secret, account=account, active=True, timeout=now() + SESSION_TIMEOUT).put()

        server_settings = get_server_settings()
        set_cookie(self.response, server_settings.cookieSessionName, secret)
        self.redirect('/', False)


class SessionCleanupHandler(webapp2.RequestHandler):

    def get(self):
        run_job(_get_session_keys, [], _cleanup_session, [])


def _get_session_keys():
    return Session.all(keys_only=True).filter("active =", True)


def _cleanup_session(session_key):

    def trans():
        session = db.get(session_key)
        if session.account == None:
            pass
        elif session.timeout > now():
            return

        session.active = False
        session.put()

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)


def get_session_by_session_cookie(request_cookies):
    server_settings = get_server_settings()
    try:
        cookie = request_cookies[server_settings.cookieSessionName]
    except KeyError:
        return None
    secret = parse_cookie(cookie)
    return Session.get_by_key_name(secret)


def get_account_by_session_cookie(request_cookies):
    session = get_session_by_session_cookie(request_cookies)
    return session and session.account or None
