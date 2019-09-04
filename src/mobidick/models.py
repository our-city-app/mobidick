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

import logging

from google.appengine.ext import db

from mcfw.cache import CachedModelMixIn, cached
from mcfw.rpc import returns, arguments
from mcfw.serialization import deserializer, ds_model, serializer, s_model, register
from model_utils import add_meta


class Account(db.Model):
    apikey = db.StringProperty(indexed=False)
    sikey = db.StringProperty()
    name = db.StringProperty(indexed=False)
    avatar = db.StringProperty(indexed=False)
    locked = db.BooleanProperty(indexed=False)
    dateTimezone = db.StringProperty(indexed=False)
    dailyResultsExport = db.StringProperty(indexed=False)

    @property
    def email(self):
        return self.key().name()


class DailyResultExport(db.Model):
    """Child model of Account, indicating when the next export must be run."""
    nextExport = db.IntegerProperty()


def get_daily_result_export_by_account(account):
    return DailyResultExport.get_by_key_name("daily_result_export", account)


def get_daily_result_exports(timestamp):
    return DailyResultExport.all().filter("nextExport <", timestamp)


class Session(db.Expando):
    account = db.ReferenceProperty(Account)
    active = db.BooleanProperty()
    timeout = db.IntegerProperty(indexed=False)
    tag = db.StringProperty()

    @property
    def secret(self):
        return self.key().name()


def get_account_by_sik(sik):
    return Account.all().filter("sikey =", sik).get()


def get_active_sessions_for_account(account):
    from mobidick.utils import now
    l = []
    for s in Session.all().filter("account =", account).filter("active =", True):
        if s.timeout > now():
            l.append(s)
    return l


class Poke(db.Model):
    tag = db.TextProperty()
    email = db.StringProperty(indexed=False)
    app_id = db.StringProperty(indexed=False)
    timestamp = db.IntegerProperty()
    service_identity = db.StringProperty(indexed=False)


class MessageFlowRun(db.Model):
    account = db.ReferenceProperty(Account)
    members = db.StringListProperty(indexed=False)
    result_emails = db.StringListProperty(indexed=False)
    result_emails_to_admins = db.BooleanProperty(indexed=False)
    result_rogerthat_account = db.StringProperty(indexed=False)
    result_branding = db.StringProperty(indexed=False)
    result_count = db.IntegerProperty(indexed=False, default=0)
    message_flow = db.StringProperty()
    message_flow_name = db.StringProperty(indexed=False)
    timestamp = db.IntegerProperty()
    description = db.StringProperty(indexed=False)
    service_identity = db.StringProperty(indexed=False, default="+default+")
    received_emails = db.StringListProperty(indexed=False)

    def to_mfr_summary(self):
        return {'description': self.description, 'key': unicode(self.key()), 'member_count': len(self.members),
                'member_result_count': self.result_count}


def get_message_flow_runs(account, cursor):
    mfrs = MessageFlowRun.all().filter("account =", account).order("-timestamp")
    if cursor:
        return mfrs.with_cursor(cursor)
    else:
        return mfrs


class MessageFlowRunResult(db.Model):
    account = db.ReferenceProperty(Account)
    member = db.StringProperty(indexed=False)
    member_name = db.StringProperty(indexed=False)
    result = db.TextProperty()
    timestamp = db.IntegerProperty()
    run = db.ReferenceProperty(MessageFlowRun)

    def to_mfmr_summary(self):
        return {'description': self.run.description, 'key': unicode(self.key()), 'timestamp': self.timestamp,
                'member': self.member}


def get_message_flow_results_from_to(account, from_, to):
    return MessageFlowRunResult.all().filter('account =', account).filter('timestamp >=', from_).filter('timestamp <',
                                                                                                        to).order(
        'timestamp')


class MessageFlowRunFollowUp(db.Model):
    user = db.StringProperty(indexed=False)
    type_ = db.StringProperty(indexed=False)
    hash_ = db.StringProperty()
    user_thread = db.StringProperty(indexed=False)
    last_user_msg = db.StringProperty(indexed=False)
    operator_thread = db.StringProperty(indexed=False)
    last_operator_msg = db.StringProperty(indexed=False)
    branding = db.StringProperty(indexed=False)
    result = db.ReferenceProperty(MessageFlowRunResult)
    user_name = db.StringProperty(indexed=False)
    user_language = db.StringProperty(indexed=False)


def get_message_flow_results(mfr):
    return MessageFlowRunResult.all().filter("run =", mfr).order("-timestamp")


def get_message_flow_member_results(account, cursor):
    mfmrs = MessageFlowRunResult.all().filter("account =", account).order("-timestamp")
    if cursor:
        return mfmrs.with_cursor(cursor)
    else:
        return mfmrs


def get_follow_up_by_hash(hash_):
    return MessageFlowRunFollowUp.all().filter("hash_", hash_).get()


class PokeTagMessageFlowLink(db.Model):
    description = db.StringProperty()
    message_flow = db.StringProperty(indexed=False)
    message_flow_name = db.StringProperty(indexed=False)
    result_emails = db.StringListProperty(indexed=False)
    result_emails_to_admins = db.BooleanProperty(indexed=False)
    result_rogerthat_account = db.StringProperty(indexed=False)
    result_branding = db.StringProperty(indexed=False)
    invite_message = db.TextProperty()

    @property
    def tag(self):
        return self.key().name()[4:]

    def to_poke_tag_summary(self):
        return {'description': self.description,
                'key': unicode(self.key()),
                'message_flow': self.message_flow,
                'tag': self.tag,
                'result_emails': ', '.join(self.result_emails),
                'result_rogerthat_account': self.result_rogerthat_account,
                'result_emails_to_identity_admins': self.result_emails_to_admins}


def get_poke_tag_message_flow_link(account):
    return PokeTagMessageFlowLink.all().ancestor(account).order("-description")


class Invite(db.Model):
    member = db.StringProperty(indexed=False)
    message_flow = db.StringProperty(indexed=False)
    message_flow_name = db.StringProperty(indexed=False)
    result_emails = db.StringListProperty(indexed=False)


class RunnerProcess(db.Model):
    pass


class Code(db.Model):
    author = db.UserProperty()
    timestamp = db.IntegerProperty()
    name = db.StringProperty()
    source = db.TextProperty()
    functions = db.StringListProperty()
    version = db.IntegerProperty()


class ServerSettings(CachedModelMixIn, db.Model):
    rogerthatAddress = add_meta(db.StringProperty(indexed=False),
                                doc="Rogerthat base URL. Eg: https://rogerth.at",
                                order=5)
    cookieSecretKey = add_meta(db.StringProperty(indexed=False),
                               doc="Secret key to encrypt the session (base64.b64encode(SECRET_KEY).decode('utf-8'))",
                               order=82)
    cookieSessionName = add_meta(db.StringProperty(indexed=False),
                                 doc="Cookie name for the session",
                                 order=83)

    firebaseApiKey = add_meta(db.StringProperty(indexed=False),
                              doc='Firebase api key',
                              order=200)
    firebaseAuthDomain = add_meta(db.StringProperty(indexed=False),
                                  doc='Firebase auth domain',
                                  order=201)
    firebaseDatabaseUrl = add_meta(db.StringProperty(indexed=False),
                                   doc='Firebase database URL',
                                   order=202)

    def invalidateCache(self):
        logging.info("ServerSettings removed from cache.")
        get_server_settings.invalidate_cache()


@deserializer
def ds_ss(stream):
    return ds_model(stream, ServerSettings)


@serializer
def s_ss(stream, server_settings):
    s_model(stream, server_settings, ServerSettings)


register(ServerSettings, s_ss, ds_ss)


@cached(1)
@returns(ServerSettings)
@arguments()
@db.non_transactional
def get_server_settings():
    ss = ServerSettings.get_by_key_name("MainSettings")
    if not ss:
        ss = ServerSettings(key_name="MainSettings")
    return ss


del ds_ss
del s_ss
