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
import uuid

from google.appengine.api.channel.channel import create_channel, send_message
from google.appengine.ext import db, deferred
from google.appengine.ext.webapp import template
from mobidick.business import get_templates_dir
from mobidick.models import Session, MessageFlowRun, get_message_flow_runs, get_message_flow_results, \
    get_message_flow_member_results, PokeTagMessageFlowLink, get_poke_tag_message_flow_link, Invite, \
    get_active_sessions_for_account, get_daily_result_export_by_account, DailyResultExport
from mobidick.session import get_account_by_session_cookie, get_session_by_session_cookie
from mobidick.utils import call_rogerthat, safe_file_name, try_encode
from pytz.gae import pytz
import webapp2


class HomeHandler(webapp2.RequestHandler):
    def get(self):
        tmpl_dir = get_templates_dir()
        path = os.path.join(tmpl_dir, 'home.html')

        account = get_account_by_session_cookie(self.request.cookies)
        if account:
            if not account.dateTimezone:
                account.dateTimezone = 'Europe/Brussels'
            self.response.out.write(template.render(path, {'account': account, 'timezones': pytz.all_timezones}))
        else:
            path = os.path.join(tmpl_dir, 'no_session.html')
            self.response.set_status(401)
            self.response.out.write(template.render(path, {}))


class OptionsHandler(webapp2.RequestHandler):
    def post(self):
        make_empty = lambda x: None if x is None or x.strip() == '' else x

        def trans():
            account = get_account_by_session_cookie(self.request.cookies)
            account.dateTimezone = self.request.get('timezone')
            account.dailyResultsExport = make_empty(self.request.get("dailyResultsExport"))
            db.put_async(account)
            daily_results_export = get_daily_result_export_by_account(account)
            if account.dailyResultsExport:
                if not daily_results_export:
                    timezone = pytz.timezone(account.dateTimezone)
                    tmp = datetime.datetime.fromtimestamp(time.time(), tz=timezone) + datetime.timedelta(1)
                    tomorrow = datetime.datetime(tmp.year, tmp.month, tmp.day, tzinfo=timezone)
                    epoch = datetime.datetime.fromtimestamp(0, tz=pytz.timezone('UTC'))
                    delta = tomorrow - epoch
                    timestamp = int(delta.total_seconds())
                    DailyResultExport(key_name='daily_result_export', parent=account, nextExport=timestamp).put()
            else:
                if daily_results_export:
                    daily_results_export.delete()

        xg_on = db.create_transaction_options(xg=True)
        db.run_in_transaction_options(xg_on, trans)
        self.redirect('/')


class MFRHandler(webapp2.RequestHandler):
    def get(self, mfr_key):
        tmpl_dir = get_templates_dir()
        account = get_account_by_session_cookie(self.request.cookies)
        if not account:
            self.response.set_status(401)
            path = os.path.join(tmpl_dir, 'no_session.html')
            self.response.out.write(template.render(path, {}))

        mfr = db.get(mfr_key)
        if not account.key() == mfr.account.key():
            self.response.set_status(401)
            path = os.path.join(tmpl_dir, 'no_session.html')
            self.response.out.write(template.render(path, {}))

        message_flow_results = list(get_message_flow_results(mfr))
        for mfmr in message_flow_results:
            mfmr.presult = json.loads(mfmr.result)
        if not self.request.get("download", None):
            path = os.path.join(tmpl_dir, 'flow_results.html')
            self.response.out.write(template.render(path, {'account': account, 'mfr': mfr,
                                                           'message_flow_member_results': message_flow_results}))
        else:
            path = os.path.join(tmpl_dir, 'flow_results_csv.tmpl')
            output = template.render(path, {'account': account, 'mfr': mfr,
                                            'message_flow_member_results': message_flow_results})
            self.response.headers['Content-Disposition'] = "attachment; filename=%s.csv" % safe_file_name(
                "flow result for %s" % mfr.description)
            encoding, output = try_encode(output, 'windows-1252', 'UTF-8')
            self.response.headers['Content-Type'] = 'text/csv; charset=' + encoding
            self.response.out.write(output)


class MFMRHandler(webapp2.RequestHandler):
    def get(self, mfmr_key):
        tmpl_dir = get_templates_dir()
        account = get_account_by_session_cookie(self.request.cookies)
        if not account:
            self.response.set_status(401)
            path = os.path.join(tmpl_dir, 'no_session.html')
            self.response.out.write(template.render(path, {}))

        mfmr = db.get(mfmr_key)
        if not account.key() == mfmr.account.key():
            self.response.set_status(401)
            path = os.path.join(tmpl_dir, 'no_session.html')
            self.response.out.write(template.render(path, {}))

        path = os.path.join(tmpl_dir, 'flow_member_result_csv.tmpl')
        output = template.render(path, {'call': json.loads(mfmr.result), 'mfmr': mfmr})
        self.response.headers['Content-Disposition'] = "attachment; filename=%s.csv" % safe_file_name(
            "member result for %s of %s" % (mfmr.run.description, mfmr.member))
        encoding, output = try_encode(output, 'windows-1252', 'UTF-8')
        self.response.headers['Content-Type'] = 'text/csv; charset=' + encoding
        self.response.out.write(output)


class APICallHandler(webapp2.RequestHandler):
    def post(self):
        method = self.request.get("method")
        parameters = self.request.get("params")

        account = get_account_by_session_cookie(self.request.cookies)
        if not account:
            self.response.set_status(401)
            return

        try:
            params = json.loads(parameters)
        except ValueError, e:
            self.response.set_status(400)
            self.response.out.write(str(e))
            return

        request, response = call_rogerthat(account.apikey, method, params, str(uuid.uuid4()), 20)
        self.response.headers['Content-Type'] = 'application/json'
        json.dump({'request': json.dumps(json.loads(request), indent=4),
                   'response': json.dumps(json.loads(response), indent=4)}, self.response.out)


class ExecuteFlowHandler(webapp2.RequestHandler):
    def post(self):
        account = get_account_by_session_cookie(self.request.cookies)
        if not account:
            self.response.set_status(401)
            return
        members = self.request.get("members")
        message_flow_id = self.request.get("message_flow_id")
        message_flow_name = self.request.get("message_flow_name")
        result_emails = self.request.get("result_emails")
        description = self.request.get("description")
        service_identity = self.request.get("service_identity")

        def parse_members():
            member = ""
            separators = " ,;\n\r"
            for c in members:
                if c in separators:
                    if member:
                        yield member
                    member = ""
                else:
                    member += c
            if member:
                yield member

        members = list(parse_members())
        result_emails = [em for em in result_emails.split(",") if em.strip()]
        self.response.headers['Content-Type'] = 'application/json'
        if not members:
            json.dump({'valid_request': False, 'error_message': 'No members specified'}, self.response.out)
            return
        if not message_flow_id:
            json.dump({'valid_request': False, 'error_message': 'No message flow specified'}, self.response.out)
            return
        request, response = call_rogerthat(account.apikey, "messaging.start_flow",
                                           {"service_identity": service_identity, "flow": message_flow_id,
                                            "members": members, "message_parent_key": None}, str(uuid.uuid4()))
        presponse = json.loads(response)
        if not presponse["result"]:
            json.dump({'valid_request': True, 'error_message': presponse["error"]["message"], 'request_success': False,
                       'request': request, 'response': response}, self.response.out)
            return
        if not description:
            d = datetime.datetime.now()
            description = "%s started on %s for %s" % (
                message_flow_name, datetime.datetime(d.year, d.month, d.day, d.hour, d.minute, d.second),
                len(members) > 0 and "%s, ..." % members[0] or members[0])

        mfr = MessageFlowRun(key_name=presponse["result"], timestamp=int(time.time()), account=account, members=members,
                             message_flow=message_flow_id, message_flow_name=message_flow_name, description=description,
                             result_emails=result_emails, service_identity=service_identity)
        mfr.put()
        json.dump({'valid_request': True, 'request_success': True, 'request': json.dumps(json.loads(request), indent=4),
                   'response': json.dumps(presponse, indent=4), 'mfr': mfr.to_mfr_summary()}, self.response.out)


class MassInviteHandler(webapp2.RequestHandler):
    def post(self):
        account = get_account_by_session_cookie(self.request.cookies)
        if not account:
            self.response.set_status(401)
            return
        members = self.request.get("members")
        message_flow_id = self.request.get("message_flow_id")
        message_flow_name = self.request.get("message_flow_name")
        result_emails = self.request.get("result_emails")
        invite_message = self.request.get("invite_message")

        def parse_members():
            member = ""
            separators = " ,;\n\r"
            for c in members:
                if c in separators:
                    if member:
                        yield member
                    member = ""
                else:
                    member += c
            if member:
                yield member

        members = list(parse_members())
        result_emails = [em for em in result_emails.split(",") if em.strip()]

        invite = Invite(parent=account)
        invite.message_flow = message_flow_id
        invite.message_flow_name = message_flow_name
        invite.result_emails = result_emails
        invite.invite_message = invite_message
        invite.put()

        deferred.defer(_schedule_invites, account, members, invite_message, message_flow_id, message_flow_name,
                       result_emails)


def _schedule_invites(account, members, invite_message, message_flow_id, message_flow_name, result_emails):
    def trans():
        count = 0
        while count < 4 and members:
            deferred.defer(_create_invite, account, members.pop(), invite_message, message_flow_id, message_flow_name,
                           result_emails)
            count += 1
        if members:
            deferred.defer(_schedule_invites, account, members, invite_message, message_flow_id, message_flow_name,
                           result_emails)

    db.run_in_transaction(trans)


def _create_invite(account, member, invite_message, message_flow_id, message_flow_name, result_emails):
    def trans():
        invite = Invite(parent=account)
        invite.message_flow = message_flow_id
        invite.message_flow_name = message_flow_name
        invite.result_emails = result_emails
        invite.invite_message = invite_message
        invite.member = member
        invite.put()
        deferred.defer(_invite, account, member, invite_message, str(invite.key()), str(uuid.uuid4()))

    db.run_in_transaction(trans)


def _invite(account, member, invite_message, tag, json_rpc_id):
    request, response = call_rogerthat(account.apikey, 'friend.invite',
                                       {'message': invite_message.strip() or None, 'tag': tag, 'email': member,
                                        'language': 'en', 'name': None}, json_rpc_id)
    for session in get_active_sessions_for_account(account):
        send_message(session.secret, json.dumps(
            {'type': 'callback', 'method': 'friend.invite', 'request': json.dumps(json.loads(request), indent=4),
             'response': json.dumps(json.loads(response), indent=4)}))


class ListMessageFlowRunsHandler(webapp2.RequestHandler):
    def get(self):
        account = get_account_by_session_cookie(self.request.cookies)
        if not account:
            self.response.set_status(401)
            return
        cursor = self.request.get("cursor", None)
        self.response.headers['Content-Type'] = 'application/json'
        query = get_message_flow_runs(account, cursor)
        mfrs = [mfr.to_mfr_summary() for mfr in query.fetch(20)]
        json.dump({'list': mfrs, 'more': len(mfrs) == 20, 'cursor': unicode(query.cursor())}, self.response.out)


class ListMessageFlowMemberResultsHandler(webapp2.RequestHandler):
    def get(self):
        account = get_account_by_session_cookie(self.request.cookies)
        if not account:
            self.response.set_status(401)
            return
        cursor = self.request.get("cursor", None)
        self.response.headers['Content-Type'] = 'application/json'
        query = get_message_flow_member_results(account, cursor)
        mfmrs = [mfmr.to_mfmr_summary() for mfmr in query.fetch(20)]
        json.dump({'list': mfmrs, 'more': len(mfmrs) == 20, 'cursor': unicode(query.cursor())}, self.response.out)


class ListPokeTagMessageFlowLinksHandler(webapp2.RequestHandler):
    def get(self):
        account = get_account_by_session_cookie(self.request.cookies)
        if not account:
            self.response.set_status(401)
            return
        self.response.headers['Content-Type'] = 'application/json'
        json.dump([link.to_poke_tag_summary() for link in get_poke_tag_message_flow_link(account)], self.response.out)


class DeletePokeTagLinkHandler(webapp2.RequestHandler):
    def post(self):
        account = get_account_by_session_cookie(self.request.cookies)
        if not account:
            self.response.set_status(401)
            return
        key = self.request.get("key", None)
        link = db.get(key)
        if link.parent_key() == account.key():
            link.delete()


class CreatePokeTagMessageFlowLinkHandler(webapp2.RequestHandler):
    def post(self):
        account = get_account_by_session_cookie(self.request.cookies)
        if not account:
            self.response.set_status(401)
            return
        self.response.headers['Content-Type'] = 'application/json'
        description = self.request.get("description")
        tag = self.request.get("tag")
        message_flow = self.request.get("message_flow")
        message_flow_name = self.request.get("message_flow_name")
        result_emails = self.request.get("result_emails")
        result_emails = [em for em in result_emails.split(",") if em.strip()]
        result_emails_to_admins = self.request.get("result_emails_to_identity_admins") == 'true'
        rogerthat_account = self.request.get("result_rogerthat_account", "").strip()
        branding = self.request.get("result_branding", "").strip()
        if rogerthat_account:
            # Checking if service is friends with this user
            is_friend = False
            _, response = call_rogerthat(account.apikey, "friend.get_status", {'email': rogerthat_account},
                                         str(uuid.uuid4()))
            presponse = json.loads(response)
            result = presponse.get('result')
            if result:
                is_friend = result.get('is_friend', False)
            if not is_friend:
                msg = '%s is no user of this service' % rogerthat_account
                json.dump({'success': False, 'message': msg}, self.response.out)
                return

        if not description:
            description = "Poke tag '%s' maps to message flow '%s'" % (tag, message_flow_name)

        key_name = "tag:%s" % tag
        link = PokeTagMessageFlowLink.get_by_key_name(key_name, parent=account)
        if link:
            json.dump({'success': False, 'message': 'A link for this tag already exists.'}, self.response.out)
            return

        link = PokeTagMessageFlowLink(key_name=key_name, parent=account, description=description,
                                      message_flow=message_flow, message_flow_name=message_flow_name,
                                      result_emails=result_emails, result_rogerthat_account=rogerthat_account,
                                      result_branding=branding, result_emails_to_admins=result_emails_to_admins)
        link.put()
        json.dump({'success': True, 'link': link.to_poke_tag_summary()}, self.response.out)


class GetChannelAPITokenHandler(webapp2.RequestHandler):
    def post(self):
        session = get_session_by_session_cookie(self.request.cookies)
        self.response.headers['Content-Type'] = 'application/json'
        json.dump({'token': create_channel(session.secret)}, self.response.out)


class ActivateSessionHandler(webapp2.RequestHandler):
    def post(self):
        session = Session.get_by_key_name(self.request.get('from'))
        session.active = True
        session.put()


class DeactivateSessionHandler(webapp2.RequestHandler):
    def post(self):
        session = Session.get_by_key_name(self.request.get('from'))
        session.active = False
        session.put()
