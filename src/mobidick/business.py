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

import base64
import datetime
import hashlib
import inspect
import json
import logging
import md5
import os
import time
import uuid

from google.appengine.api.channel.channel import send_message
from google.appengine.ext import deferred, db
from google.appengine.ext.webapp import template
from mobidick.models import get_account_by_sik, get_active_sessions_for_account, MessageFlowRun, MessageFlowRunResult, \
    PokeTagMessageFlowLink, Invite, RunnerProcess, MessageFlowRunFollowUp, Poke
from mobidick.translations import localize
from mobidick.utils import call_rogerthat, try_encode, send_mail, now
from pytz.gae import pytz


TYPE_MAIL = 'mail'
TYPE_ROGERTHAT = 'rogerthat'
TAG_OPERATOR_MSG = 'o='
TAG_ENDUSER_MSG = 'u1='
TAG_ENDUSER_MSG_WITH_BUTTONS = 'u2='
BUTTONS_LINE = "## Each line below will result in a quick answer button ##"
HASHES = "#" * len(BUTTONS_LINE)


def call(request, sik):
    response = dict()
    method = request["method"]
    id_ = request["id"]
    response["id"] = id_
    logging.info("Incoming Rogerth.at callback method %(method)s with id %(id_)s." % locals())
    m = getattr(inspect.getmodule(test_test), method.replace(".", "_"), None)
    if not m:
        response["result"] = None
        response["error"] = None
    else:
        try:
            params = dict()
            for p, v in request["params"].iteritems():
                params[str(p)] = v
            response["result"] = m(sik, id_, **params)
            response["error"] = None
            logging.info("Incoming Rogerth.at callback method %(method)s executed successfully." % locals())
        except Exception, e:
            response["result"] = None
            response["error"] = str(e)
            logging.exception("Incoming Rogerth.at callback method %(method)s failed." % locals())
    account = get_account_by_sik(sik)
    if account:
        for session in get_active_sessions_for_account(account):
            send_message(session.secret, json.dumps({'type': 'callback',
                                                     'method': method,
                                                     'request': json.dumps(request, indent=4),
                                                     'response': json.dumps(response, indent=4)}))
    return response

def test_test(sik, id_, value, **kwargs):
    return value

def friend_invited(sik, id_, **kwargs):
    return "accepted"

def friend_is_in_roles(sik, id_, **kwargs):
    return [r['id'] for r in kwargs['roles']]

def messaging_update(sik, id_, **kwargs):
    account = get_account_by_sik(sik)
    if not account:
        return

    tag = kwargs['tag']
    pkey = kwargs['parent_message_key']
    mkey = kwargs['message_key']
    member = kwargs['member']
    status = kwargs['status']
    answer_id = kwargs['answer_id']

    def trans():
        rp = RunnerProcess.get_by_key_name(id_, parent=account)
        if rp:
            logging.warning("Skipping duplicate messaging.form_update")
            return
        RunnerProcess(key_name=id_, parent=account).put()
        deferred.defer(_message_update, account, tag, pkey, mkey, member, status, answer_id, _transactional=True)
    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)


def _message_update(account, tag, pkey, mkey, member, status, answer_id):
    if not tag or not any(filter(lambda t: tag.startswith(t), (TAG_OPERATOR_MSG, TAG_ENDUSER_MSG, TAG_ENDUSER_MSG_WITH_BUTTONS))):
        return

    if status < 2:
        return

    def trans():
        mfr_fu = MessageFlowRunFollowUp.get(json.loads(tag.split('=', 1)[1])['k'])
        mfr = mfr_fu.parent()
        if tag.startswith(TAG_OPERATOR_MSG):
            if answer_id and answer_id == 'reply':
                mfr_fu.last_operator_msg = None
                mfr_fu.put()

                # LOCK MESSAGE
                deferred.defer(_seal_message, account, str(uuid.uuid4()), pkey, mkey, mfr.service_identity, _transactional=True)

                # SEND TEXT_BLOCK TO OPERATOR
                message = "Enter your reply to %s" % mfr_fu.user
                new_tag = "%s%s" % (TAG_OPERATOR_MSG, json.dumps({'k':str(mfr_fu.key())}))
                deferred.defer(_send_text_block, account, str(uuid.uuid4()), pkey or mkey, message,
                               "\n\n%s\n%s\n" % ("#" * len(BUTTONS_LINE), BUTTONS_LINE), member, new_tag, mfr.service_identity,
                               target_language=None, _transactional=True)

        else:
            if tag.startswith(TAG_ENDUSER_MSG_WITH_BUTTONS):
                if mfr_fu.last_operator_msg:
                    # LOCK LAST MSG IN OPERATOR THREAD
                    deferred.defer(_seal_message, account, str(uuid.uuid4()), mfr_fu.operator_thread,
                                   mfr_fu.last_operator_msg, mfr.service_identity, _transactional=True)
                    mfr_fu.last_operator_msg = None

                # ENDUSER PRESSED A CUSTOM BUTTON, SEND ANSWER TO OPERATOR
                message = "%s pressed button: '%s'" % (mfr_fu.user, answer_id or "Roger that!")
                new_tag = "%s%s" % (TAG_OPERATOR_MSG, json.dumps({'k':str(mfr_fu.key())}))
                deferred.defer(_send_followup_message, account, str(uuid.uuid4()), mfr_fu.operator_thread, message,
                               [get_reply_button(None)], [], new_tag, mfr.service_identity, _transactional=True)
            else:
                if answer_id == 'reply':  # ENDUSER PRESSED REPLY BUTTON
                    mfr_fu.last_user_msg = None

                    # LOCK MESSAGE
                    deferred.defer(_seal_message, account, str(uuid.uuid4()), pkey, mkey, mfr.service_identity, _transactional=True)

                    # SEND TEXT BLOCK TO ENDUSER
                    message = "Enter your reply below:"
                    new_tag = "%s%s" % (TAG_ENDUSER_MSG, json.dumps({'k':str(mfr_fu.key())}))
                    deferred.defer(_send_text_block, account, str(uuid.uuid4()), pkey, message, None, member,
                                   new_tag, mfr.service_identity, mfr_fu.user_language, mfr_fu.branding, _transactional=True)

                else:  # ENDUSER PRESSED ROGERTHAT BUTTON
                    if mfr_fu.last_operator_msg:
                        # LOCK LAST MSG IN OPERATOR THREAD
                        deferred.defer(_seal_message, account, str(uuid.uuid4()), mfr_fu.operator_thread,
                                       mfr_fu.last_operator_msg, mfr.service_identity, _transactional=True)
                        mfr_fu.last_operator_msg = None

                    # REPORT TO OPERATOR
                    message = "%s pressed the Roger that! button" % mfr_fu.user
                    new_tag = "%s%s" % (TAG_OPERATOR_MSG, json.dumps({'k':str(mfr_fu.key())}))
                    deferred.defer(_send_followup_message, account, str(uuid.uuid4()), mfr_fu.operator_thread, message,
                                   [get_reply_button(None)], [], new_tag, mfr.service_identity, _transactional=True)
            mfr_fu.put()
    db.run_in_transaction(trans)


def messaging_form_update(sik, id_, **kwargs):
    account = get_account_by_sik(sik)
    if not account:
        return

    tag = kwargs['tag']
    pkey = kwargs['parent_message_key']
    mkey = kwargs['message_key']
    member = kwargs['member']
    form_result = kwargs['form_result']
    answer_id = kwargs['answer_id']

    def trans():
        rp = RunnerProcess.get_by_key_name(id_, parent=account)
        if rp:
            logging.warning("Skipping duplicate messaging.form_update")
            return
        RunnerProcess(key_name=id_, parent=account).put()
        deferred.defer(_form_update, account, tag, pkey, mkey, member, form_result, answer_id, _transactional=True)
    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)

def get_reply_button(target_language):
    return {'id': 'reply', 'caption': localize(target_language, "Reply"), 'ui_flags': 1}

def send_to_end_user(account, answer, mfr_fu):
    buttons = list()
    lines = answer.splitlines()
    button_line_found = False
    for l in lines:
        if l == BUTTONS_LINE:
            button_line_found = True
        elif button_line_found and l.strip():
            buttons.append({'id':l, 'caption':l})

    if HASHES in answer:
        answer = answer[:answer.index(HASHES)]
    new_tag = "%s%s" % (TAG_ENDUSER_MSG_WITH_BUTTONS if buttons else TAG_ENDUSER_MSG, json.dumps({'k':str(mfr_fu.key())}))
    auto_lock = bool(buttons)
    if not buttons:
        buttons.append(get_reply_button(mfr_fu.user_language))
    mfr = mfr_fu.parent()
    deferred.defer(_send_followup_message, account, str(uuid.uuid4()), mfr_fu.user_thread, answer.strip(), buttons,
                   [mfr_fu.user], new_tag, mfr.service_identity, auto_lock=auto_lock, branding=mfr_fu.branding,
                   _transactional=db.is_in_transaction())

def _form_update(account, tag, pkey, mkey, member, form_result, answer_id):
    if not tag or not any(filter(lambda t: tag.startswith(t), (TAG_OPERATOR_MSG, TAG_ENDUSER_MSG))):
        return

    def trans():
        answer = ''
        if form_result and 'result' in form_result:
            answer = form_result['result'].get('value', '')

        if tag.startswith(TAG_OPERATOR_MSG):
            mfr_fu = MessageFlowRunFollowUp.get(json.loads(tag.split('=', 1)[1])['k'])
            mfr = mfr_fu.parent()
            logging.info("Operator replied to end user")

            should_send_to_enduser = answer_id == 'positive' and answer.replace(HASHES, '').replace(BUTTONS_LINE, '').strip()

            # SEND MESSAGE TO ENDUSER
            if should_send_to_enduser:
                send_to_end_user(account, answer, mfr_fu)

            # SEND REPORT TO OPERATOR
            if should_send_to_enduser:
                message = "Message sent to %s.\nPress Reply to send another message." % mfr_fu.user
            elif answer_id == 'positive':
                message = "You tried to send an empty message to %s. No message was sent." % mfr_fu.user
            else:
                message = "You canceled the reply, no message was sent to %s" % mfr_fu.user
            new_tag = "%s%s" % (TAG_OPERATOR_MSG, json.dumps({'k':str(mfr_fu.key())}))
            deferred.defer(_send_followup_message, account, str(uuid.uuid4()), mfr_fu.operator_thread, message,
                           [get_reply_button(None)], list(), new_tag, mfr.service_identity, _transactional=True)

        elif tag.startswith(TAG_ENDUSER_MSG):
            mfr_fu = MessageFlowRunFollowUp.get(json.loads(tag.split('=', 1)[1])['k'])
            mfr = mfr_fu.parent()
            logging.info("End user answered on an operator's message")

            if mfr_fu.last_operator_msg:
                # LOCK LAST MSG IN OPERATOR THREAD
                deferred.defer(_seal_message, account, str(uuid.uuid4()), mfr_fu.operator_thread, mfr_fu.last_operator_msg,
                               mfr.service_identity, _transactional=True)
                mfr_fu.last_operator_msg = None
                mfr_fu.put()

            # SEND REPORT TO OPERATORS
            if answer_id == 'positive':
                message = "%s replied with:\n%s" % (member, answer)
            else:
                message = "%s pressed the red Cancel button" % member
            if mfr_fu.type_ == TYPE_MAIL:
                mfr = mfr_fu.parent()

                admin_emails = list()
                if mfr.result_emails_to_admins:
                    admin_emails = _get_service_identity_admin_emails(account, mfr.service_identity)

                if admin_emails or mfr.result_emails:
                    send_mail("%s <%s.followup@mobidick-cloud.appspotmail.com>" % (account.name, mfr_fu.hash_),
                              list(set(mfr.result_emails + admin_emails)), "RE: Flow member result of %s for %s" % (member, mfr.message_flow_name),
                              message)
            else:
                mfr = mfr_fu.parent()
                new_tag = "%s%s" % (TAG_OPERATOR_MSG, json.dumps({'k':str(mfr_fu.key())}))
                deferred.defer(_send_followup_message, account, str(uuid.uuid4()), mfr_fu.operator_thread, message,
                               [get_reply_button(None)], list(), new_tag, mfr.service_identity, _transactional=True)
    db.run_in_transaction(trans)

def messaging_flow_member_result(sik, id_, **kwargs):
    account = get_account_by_sik(sik)
    if not account:
        return

    def trans():
        rp = RunnerProcess.get_by_key_name(id_, parent=account)
        if rp:
            logging.warning("Skipping duplicate messaging.flow_member_result")
            return
        RunnerProcess(key_name=id_, parent=account).put()
        deferred.defer(_flow_member_result, account, kwargs.copy(), _transactional=True)
    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)

def _flow_member_result(account, kwargs):
    mfr_id = kwargs["message_flow_run_id"]
    mfr = MessageFlowRun.get_by_key_name(mfr_id)
    if not mfr:
        return
    if account.key() != mfr.account.key():
        logging.error("flow_member result received from unmatched account.\nExpected account: %s\nReceived account: %s" \
                      % (mfr.account.name, account.name))
        return

    member = kwargs["member"]

    _, response = call_rogerthat(account.apikey, 'friend.get_status', {"email": member}, str(uuid.uuid4()))
    presponse = json.loads(response)
    if presponse["result"]:
        name = presponse["result"]["name"]
        language = presponse["result"]["language"]
    else:
        name = None
        language = None

    if not account.dateTimezone:
        timezone = pytz.timezone('Europe/Brussels')
    else:
        timezone = pytz.timezone(account.dateTimezone)

    for step in kwargs['steps']:
        try:
            logging.info(step)
            if "message" in step:
                message = step["message"]
                if message.startswith("base64:"):
                    message = base64.decodestring(message[7:])
                    step["message"] = message
            if "display_value" in step:
                display_value = step["display_value"]
                if display_value:
                    if display_value.startswith("base64:"):
                        display_value = base64.decodestring(display_value[7:])
                        step["display_value"] = display_value
                    if "<date_value/>" in display_value:
                        display_value = display_value \
                            .replace("<date_value/>",
                                     datetime.datetime.fromtimestamp(step["form_result"]["result"]["value"], tz=timezone).strftime("%b %d %Y"))
                    elif "<time_value/>" in display_value:
                        display_value = display_value \
                            .replace("<time_value/>",
                                     datetime.datetime.fromtimestamp(step["form_result"]["result"]["value"], tz=timezone).strftime("%H:%M"))
                    elif "<date_time_value/>" in display_value:
                        display_value = display_value \
                            .replace("<date_time_value/>",
                                     datetime.datetime.fromtimestamp(step["form_result"]["result"]["value"], tz=timezone).strftime("%b %d %Y %H:%M"))
                step["display_value"] = '' if display_value is None else display_value
        except:
            logging.exception("Error while trying correctly display selected time.")

    def trans():
        mfmr = MessageFlowRunResult(key_name="%s-%s" % (mfr_id, member), member=member, member_name=name, run=mfr,
                                    result=json.dumps(kwargs, indent=4), timestamp=int(time.time()), account=account,
                                    service_identity=kwargs["service_identity"])
        db.put_async(mfmr)
        deferred.defer(_update_result_count, mfr.key(), mfmr, _transactional=True)
        if mfr.result_emails or mfr.result_emails_to_admins:
            mfr_fu = MessageFlowRunFollowUp(parent=mfr, user_thread=kwargs["parent_message_key"], user=kwargs["member"],
                                            branding=mfr.result_branding, type_=TYPE_MAIL, result=mfmr, user_name=name,
                                            user_language=language)
            mfr_fu.put()
            mfr_fu.hash_ = hashlib.sha256(str(mfr_fu.key())).hexdigest()
            mfr_fu.put()

            deferred.defer(_send_mail_for_message_flow_run_result, mfr, mfr_fu, mfmr, account,
                           member, name, kwargs, _transactional=True)

        if mfr.result_rogerthat_account:
            deferred.defer(_mfmr_follow_up, account, mfr, mfmr.key(), name, language, kwargs, int(time.time()), _transactional=True)

    xg_on = db.create_transaction_options(xg=True)
    db.run_in_transaction_options(xg_on, trans)

def _get_service_identity_admin_emails(account, service_identity):
    _, response = call_rogerthat(account.apikey, "system.get_info", {'service_identity':service_identity}, str(uuid.uuid4()))
    result = json.loads(response).get('result')
    admin_emails = []
    if result:
        admin_emails = result.get('admin_emails', [])
    return admin_emails

def get_templates_dir():
    return os.path.join(os.path.dirname(__file__), 'templates')

def _send_mail_for_message_flow_run_result(mfr, mfr_fu, mfmr, account, member, name, kwargs):
    tmpl_dir = get_templates_dir()
    path = os.path.join(tmpl_dir, 'flow_member_result.tmpl')
    body = template.render(path, {'call':kwargs, 'timestamp': int(time.time()), 'mfr': mfr, 'name': name})
    path = os.path.join(tmpl_dir, 'flow_member_result_html.tmpl')
    body_html = template.render(path, {'call':kwargs, 'timestamp': int(time.time()), 'mfr': mfr, 'name': name})
    path = os.path.join(tmpl_dir, 'flow_member_result_csv.tmpl')
    _, csv = try_encode(template.render(path, {'call':kwargs, 'mfmr': mfmr}), 'windows-1252', 'UTF-8')

    admin_emails = list()
    if mfr.result_emails_to_admins:
        admin_emails = _get_service_identity_admin_emails(account, mfr.service_identity)

    logging.info(body)
    if admin_emails or mfr.result_emails:
        send_mail("%s <%s.followup@mobidick-cloud.appspotmail.com>" % (account.name, mfr_fu.hash_),
                  list(set(mfr.result_emails + admin_emails)), "Flow member result of %s for %s" % (member, mfr.message_flow_name),
                  body, attachments=[('results.csv', csv)], html=body_html)

def _mfmr_follow_up(account, mfr, mfmr_key, name, language, kwargs, timestamp):
    tmpl_dir = get_templates_dir()
    mfmr = db.get(mfmr_key)
    def trans():
        logging.info("Send MFR result as rogerthat message so operators can communicate with the member")
        path = os.path.join(tmpl_dir, 'flow_member_result_message.tmpl')
        body = template.render(path, {'call':kwargs, 'timestamp': timestamp, 'mfr': mfr})
        mfr_fu = MessageFlowRunFollowUp(parent=mfr, user_thread=kwargs["parent_message_key"], user=kwargs["member"],
                                        branding=mfr.result_branding, type_=TYPE_ROGERTHAT, result=mfmr, user_name=name,
                                        user_language=language)
        mfr_fu.put()
        mfr_fu.hash_ = hashlib.sha256(str(mfr_fu.key())).hexdigest()
        mfr_fu.put()
        tag = "%s%s" % (TAG_OPERATOR_MSG, json.dumps({'k':str(mfr_fu.key())}))
        deferred.defer(_send_followup_message, account, str(uuid.uuid4()), parent_key=None, message=body,
                       buttons=[get_reply_button(None)], to=[mfr.result_rogerthat_account], tag=tag,
                       service_identity=mfr.service_identity, new_mfr_fu=mfr_fu,
                       _transactional=True)
    db.run_in_transaction(trans)


def messaging_poke(sik, id_, **kwargs):
    logging.info("Incoming poke call for sik %s" % sik)
    account = get_account_by_sik(sik)
    if not account:
        logging.info("Sik not recognized")
        return

    tag = kwargs['tag']
    email = kwargs["email"]
    app_id = kwargs["user_details"][0]["app_id"]
    result_key = kwargs["result_key"]
    service_identity = kwargs["service_identity"]

    rpc = db.put_async(Poke(key_name=result_key, parent=account, email=email, app_id=app_id, tag=tag, timestamp=now(),
                            service_identity=service_identity))

    key_name = "tag:"
    if tag != None:
        key_name += tag
    link = PokeTagMessageFlowLink.get_by_key_name(key_name, parent=account)
    if not link:
        return
    flow = link.message_flow
    _try_or_defer(_store_mfr, email, tag, link, result_key, account, kwargs["service_identity"])
    rpc.get_result()  # Prevent warnings.
    return dict(type='flow', value=dict(flow=flow))

def _store_mfr(email, tag, link, result_key, account, service_identity):
    def trans():
        description = "%s poked %s ==> %s" % (email, "" if tag is None else tag, link.message_flow_name)
        mfr = MessageFlowRun(key_name=result_key, timestamp=int(time.time()), account=account,
                             members=[email], message_flow=link.message_flow, message_flow_name=link.message_flow_name,
                             description=description, result_emails=link.result_emails,
                             result_rogerthat_account=link.result_rogerthat_account, result_branding=link.result_branding,
                             result_emails_to_admins=link.result_emails_to_admins, service_identity=service_identity)
        mfr.put()
    db.run_in_transaction(trans)

def friend_invite_result(sik, id_, **kwargs):
    result = kwargs["result"]
    tag = kwargs["tag"]
    email = kwargs["email"]
    service_identity = kwargs["service_identity"]

    account = get_account_by_sik(sik)
    if not account:
        return

    try:
        invite = Invite.get(tag)
    except:
        invite = None  # Invite originating from eg QR-Code scan

    if not invite:
        return

    if invite.parent_key() != account.key():
        logging.error("friend.invite_result received from unmatched account.\nExpected account: %s\nReceived account: %s" \
                      % (db.get(invite.parent_key()).name, account.name))
        return

    if result == "accepted":
        if invite.message_flow:
            deferred.defer(_send_message_flow, account, invite, email, str(uuid.uuid4()), service_identity)
        if invite.result_emails:
            subject = "%s accepted your invitation with his %s Rogerthat account." % (invite.member, email)
            send_mail("%s <notifications@mobidick-cloud.appspotmail.com>" % account.name, invite.result_emails,
                           subject, subject)
    else:
        if invite.result_emails:
            subject = "%s declined your invitation." % invite.member
            send_mail("%s <notifications@mobidick-cloud.appspotmail.com>" % account.name, invite.result_emails,
                           subject, subject)

def _try_or_defer(method, *args):
    try:
        method(*args)
    except:
        logging.exception("Failed to execute method, deferring.")
        deferred.defer(method, *args)

def _gen_callid(callid, sik, kind):
    h = md5.md5(sik)
    h.update(callid)
    h.update(kind)
    return h.hexdigest()

def _send_message_flow(account, invite, email, json_rpc_id, service_identity):
    def trans():
        request, response = call_rogerthat(account.apikey, "messaging.start_flow",
                                           {'flow': invite.message_flow, "members": [email], "message_parent_key": None},
                                           json_rpc_id)
        presponse = json.loads(response)
        if not presponse["result"]:
            json.dump({'valid_request': True, 'error_message': presponse["error"]["message"], 'request_success': False,
                       'request':request, 'response': response}, response.out)
            return
        description = "%s started on invite follow up for %s" % (invite.message_flow_name, email)
        mfr = MessageFlowRun(key_name=presponse["result"], timestamp=int(time.time()), account=account, members=[email],
                             message_flow=invite.message_flow, message_flow_name=invite.message_flow_name,
                             description=description, result_emails=invite.result_emails, service_identity=service_identity)
        mfr.put()
        return request, presponse
    request, presponse = db.run_in_transaction(trans)
    for session in get_active_sessions_for_account(account):
        send_message(session.secret, json.dumps({'type': 'callback',
                                                 'method': 'messaging.start_flow',
                                                 'request': json.dumps(json.loads(request), indent=4),
                                                 'response': json.dumps(presponse, indent=4)}))

def _update_result_count(mfr_key, mfmr):
    def trans():
        mfr = db.get(mfr_key)
        mfr.result_count += 1
        mfr.put()
        return mfr
    mfr = db.run_in_transaction(trans)
    for session in get_active_sessions_for_account(mfr.account):
        send_message(session.secret, json.dumps({'type': 'mfr_update',
                                                 'mfr': mfr.to_mfr_summary(),
                                                 'mfmr': mfmr.to_mfmr_summary()}))

def _send_text_block(account, json_rpc_id, parent_key, message, text_value, to, tag, service_identity, target_language, branding=None):
    params = {
        "member": to,
        "tag": tag,
        "message": message,
        "parent_key": parent_key,
        "branding": branding,
        "flags": 30,
        "service_identity": service_identity,
        "form": {
             "positive_button": localize(target_language, "Send"),
             "positive_button_ui_flags": 1 if tag.startswith(TAG_OPERATOR_MSG) else 0,
             "negative_button": localize(target_language, "Cancel"),
             "negative_button_ui_flags": 1 if tag.startswith(TAG_OPERATOR_MSG) else 0,
             "type": "text_block",
             "widget": {
                 "value": text_value,
                 "max_chars": 8000
             }
        }
    }
    logging.info("Proxy message to %s: \n\n%s\n\n" % (to, params))
    request, response = call_rogerthat(account.apikey, "messaging.send_form", params, json_rpc_id)
    for session in get_active_sessions_for_account(account):
        send_message(session.secret, json.dumps({'type': 'callback',
                                                 'method': 'messaging.send_form',
                                                 'request': json.dumps(json.loads(request), indent=4),
                                                 'response': json.dumps(json.loads(response), indent=4)}))

def _send_followup_message(account, json_rpc_id, parent_key, message, buttons, to, tag, service_identity,
                           new_mfr_fu=None, auto_lock=False, branding=None):
    params = {
        "members": to,
        "tag": tag,
        "message": message,
        "parent_key": parent_key,
        "branding": branding,
        "sender_answer": None,
        "service_identity": service_identity,
        "flags": 95 if auto_lock else 31,
        "answers": []
    }
    for btn in buttons:
        params["answers"].append({
                "type": "button",
                "id": btn["id"],
                "caption": btn["caption"],
                "action": None,
                "ui_flags": btn.get('ui_flags', 0)
        })
    logging.info("Follow-up message to %s: \n\n%s\n\n" % (to, params))
    request, response = call_rogerthat(account.apikey, "messaging.send", params, json_rpc_id)
    request = json.loads(request)
    response = json.loads(response)

    if not response['error']:
        msg_key = response['result']
        mfr_fu = new_mfr_fu or MessageFlowRunFollowUp.get(json.loads(tag.split('=', 1)[1])['k'])
        if tag.startswith(TAG_OPERATOR_MSG):
            if not mfr_fu.operator_thread:
                mfr_fu.operator_thread = msg_key
            mfr_fu.last_operator_msg = msg_key
            mfr_fu.put()
        else:
            mfr_fu.last_user_msg = msg_key
            mfr_fu.put()

    for session in get_active_sessions_for_account(account):
        send_message(session.secret, json.dumps({'type': 'callback',
                                                 'method': 'messaging.send',
                                                 'request': json.dumps(request, indent=4),
                                                 'response': json.dumps(response, indent=4)}))

def _seal_message(account, json_rpc_id, parent_key, message_key, service_identity):
    params = {
        "parent_message_key": parent_key,
        "message_key": message_key,
        "service_identity": service_identity,
        "dirty_behavior": 3  # Clear dirty flag
    }
    logging.info("Seal message: \n\n%s\n\n" % params)
    request, response = call_rogerthat(account.apikey, "messaging.seal", params, json_rpc_id)
    for session in get_active_sessions_for_account(account):
        send_message(session.secret, json.dumps({'type': 'callback',
                                                 'method': 'messaging.seal',
                                                 'request': json.dumps(json.loads(request), indent=4),
                                                 'response': json.dumps(json.loads(response), indent=4)}))

def system_api_call(sik, id_, **kwargs):
    return dict(error=None, result=None)
