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

import Cookie
import base64
import email.utils
import hashlib
import hmac
import logging
import time

from consts import DEBUG, SESSION_TIMEOUT
from mobidick.models import get_server_settings


#### Copied from https://github.com/facebook/python-sdk/blob/master/examples/oauth/facebookoauth.py ####
def set_cookie(response, name, value, domain=None, path="/", expires=None):
    """Generates and signs a cookie for the give name/value"""
    if not isinstance(name, str):
        name = name.encode("utf8")
    timestamp = unicode(int(time.time()))
    value = base64.b64encode(value)
    signature = cookie_signature(value, timestamp)
    cookie = Cookie.BaseCookie()
    cookie[name] = "|".join([value, timestamp, signature])
    cookie[name]["path"] = path
    if not DEBUG:
        cookie[name]["secure"] = True
    if domain: cookie[name]["domain"] = domain
    if expires:
        cookie[name]["expires"] = email.utils.formatdate(expires, localtime=False, usegmt=True)
    response.headers.add_header("Set-Cookie", cookie.output()[12:] + '; httponly')


def parse_cookie(value):
    """Parses and verifies a cookie value from set_cookie"""
    if not value: return None
    parts = value.split("|")
    if len(parts) != 3: return None
    if cookie_signature(parts[0], parts[1]) != parts[2]:
        logging.warning("Invalid cookie signature %r", value)
        return None
    timestamp = int(parts[1])
    if timestamp < time.time() - SESSION_TIMEOUT:
        logging.warning("Expired cookie %r", value)
        return None
    try:
        return base64.b64decode(parts[0]).strip()
    except:
        return None


def cookie_signature(*parts):
    """Generates a cookie signature."""
    server_settings = get_server_settings()
    secret = base64.b64decode(server_settings.cookieSecretKey.encode("utf8"))
    if not secret:
        raise Exception('Server setting "secret" is not set')
    hash_ = hmac.new(unicode(secret), digestmod=hashlib.sha1)
    for part in parts: hash_.update(part)
    return hash_.hexdigest()

#### End copied ####
