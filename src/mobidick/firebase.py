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

import base64
import json
import logging
import time

from google.appengine.api.app_identity import app_identity
import httplib2
from oauth2client.client import GoogleCredentials
import webapp2

from mobidick.models import get_server_settings
from mobidick.utils import now

try:
    from functools import lru_cache
except ImportError:
    from functools32 import lru_cache

_IDENTITY_ENDPOINT = ('https://identitytoolkit.googleapis.com/'
                      'google.identity.identitytoolkit.v1.IdentityToolkit')
_FIREBASE_SCOPES = [
    'https://www.googleapis.com/auth/firebase.database',
    'https://www.googleapis.com/auth/userinfo.email']


@lru_cache()
def _get_firebase_db_url():
    return get_server_settings().firebaseDatabaseUrl


# Memoize the authorized http, to avoid fetching new access tokens
@lru_cache()
def _get_http():
    """Provides an authenticated http object."""
    http = httplib2.Http()
    # Use application default credentials to make the Firebase calls
    # https://firebase.google.com/docs/reference/rest/database/user-auth
    creds = GoogleCredentials.get_application_default().create_scoped(_FIREBASE_SCOPES)
    creds.authorize(http)
    return http


def create_firebase_auth_token(uid, valid_minutes=60):
    """Create a secure token for the given uid.
    This method is used to create secure custom JWT tokens to be passed to
    clients. It takes a unique id (uid) that will be used by Firebase's
    security rules to prevent unauthorized access. In this case, the uid will
    be the channel id which is a combination of user_id and a guid
    """
    if valid_minutes > 60:
        raise Exception('Firebase tokens can only be valid for maximum 60 minutes')
    # use the app_identity service from google.appengine.api to get the
    # project's service account email automatically
    client_email = app_identity.get_service_account_name()

    now = int(time.time())
    # encode the required claims
    # per https://firebase.google.com/docs/auth/server/create-custom-tokens
    payload = base64.b64encode(json.dumps({
        'iss': client_email,
        'sub': client_email,
        'aud': _IDENTITY_ENDPOINT,
        'uid': uid,
        'iat': now,
        'exp': now + (valid_minutes * 60),
    }))
    # add standard header to identify this as a JWT
    header = base64.b64encode(json.dumps({'typ': 'JWT', 'alg': 'RS256'}))
    to_sign = '%s.%s' % (header, payload)
    # Sign the jwt using the built in app_identity service
    return '%s.%s' % (to_sign, base64.b64encode(app_identity.sign_blob(to_sign)[1]))


def send_firebase_message(uid, data):
    db_url = _get_firebase_db_url()
    if not db_url:
        logging.warn('Not sending channel update, firebase is not configured properly')
        return
    message = json.dumps({
        'data': data,
        'timestamp': now()
    })

    path = '{}/channels/{}.json'.format(db_url, uid)
    return _get_http().request(path, 'PATCH', body=message)


def get_firebase_params(uid):
    server_settings = get_server_settings()
    token = create_firebase_auth_token(uid)
    params = {}
    params['firebase_api_key'] = server_settings.firebaseApiKey
    params['firebase_auth_domain'] = server_settings.firebaseAuthDomain
    params['firebase_database_url'] = server_settings.firebaseDatabaseUrl
    params['firebase_token'] = token
    params['firebase_uid'] = uid
    return params


def cleanup_firebase():
    logging.info('Removing all channel data')
    url = '%s/channel.json' % _get_firebase_db_url()
    _get_http().request(url, 'DELETE')


class FirebaseCleanupHandler(webapp2.RequestHandler):

    def get(self):
        cleanup_firebase()
