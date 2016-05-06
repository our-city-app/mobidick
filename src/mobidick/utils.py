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

import datetime
import json
import os
import time

from google.appengine.api import urlfetch, mail
from google.appengine.ext import deferred, db


def call_rogerthat(api_key, method, params, json_rpc_id, deadline=5):
    debug = os.environ["SERVER_SOFTWARE"].startswith('Development') if "SERVER_SOFTWARE" in os.environ else True
    if debug:
        url = "http://%s:8080/api/1" % os.environ["SERVER_NAME"]
    else:
        url = "https://mobicagecloudhr.appspot.com/api/1"

    payload = json.dumps({'id':json_rpc_id, 'method': method, 'params': params})

    result = urlfetch.fetch(url, \
        payload=payload, \
        method='POST', \
        headers={'Content-Type':'application/json-rpc', 'X-Nuntiuz-API-Key': api_key}, \
        allow_truncated=False, \
        follow_redirects=False,
        deadline=deadline)

    count = 1

    while result.status_code not in (200, 401):
        result = urlfetch.fetch(url, \
            payload=payload, \
            method='POST', \
            headers={'Content-Type':'application/json-rpc', 'X-Nuntiuz-API-Key': api_key}, \
            allow_truncated=False, \
            follow_redirects=False)
        count += 1
        if count == 5:
            break

    if result.status_code not in (200, 401):
        raise ValueError("Could not call Rogerthat API!")

    return payload, result.content

def safe_file_name(filename):
    safe = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.0123456789"
    return str("".join((l in safe and l or "_" for l in filename)))

def try_encode(bytez, preferred_encoding, fallback_encoding):
    try:
        return preferred_encoding, bytez.encode(preferred_encoding)
    except UnicodeEncodeError:
        return fallback_encoding, bytez.encode(fallback_encoding)

def azzert(value, message=None):
    if not value:
        raise AssertionError(message)

def send_mail(sender, to, *args, **kwargs):
    kwargs['_transactional'] = db.is_in_transaction()
    deferred.defer(_send_mail, sender, to, *args, **kwargs)

def _send_mail(sender, to, *args, **kwargs):
    if not isinstance(to, list):
        to = [to]
    for recipient in to:
        mail.send_mail(sender, recipient, *args, **kwargs)

def now():
    return int(time.time())

def strptime(val):
    '''snippet from http://stackoverflow.com/questions/3408494/string-to-datetime-with-fractional-seconds-on-google-app-engine'''
    if '.' not in val:
        return datetime.datetime.strptime(val, "%Y-%m-%dT%H:%M:%S")

    nofrag, frag = val.split(".")
    date = datetime.datetime.strptime(nofrag, "%Y-%m-%dT%H:%M:%S")

    frag = frag[:6]  # truncate to microseconds
    frag += (6 - len(frag)) * '0'  # add 0s
    return date.replace(microsecond=int(frag))


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in xrange(0, len(l), n):
        yield l[i:i + n]
