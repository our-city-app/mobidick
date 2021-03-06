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

from google.appengine.ext import webapp
from google.appengine.ext.deferred.deferred import TaskHandler
import webapp2

from mobidick.explorer import CompileRequestHandler, ExplorerPage, DeleteCodeRequestHandler, GetCodeRequestHandler, \
    RunCodeRequestHandler
from mobidick.firebase import FirebaseCleanupHandler
from mobidick.home import HomeHandler, APICallHandler, GetChannelAPITokenHandler, ExecuteFlowHandler, \
    ListMessageFlowRunsHandler, MFRHandler, \
    ListMessageFlowMemberResultsHandler, MFMRHandler, CreatePokeTagMessageFlowLinkHandler, \
    ListPokeTagMessageFlowLinksHandler, DeletePokeTagLinkHandler, MassInviteHandler, OptionsHandler
from mobidick.receiver import CallbackRequestHTTPHandler
from mobidick.session import CreateSessionRequestHandler, SessionCleanupHandler
from mobidick.settings import ServerSettingsHandler


webapp.template.register_template_library('mobidick.templates.filters')

mapping = [
    ('/', HomeHandler),
    ('/_ah/queue/deferred', TaskHandler),
    ('/options', OptionsHandler),
    ('/create_session', CreateSessionRequestHandler),
    ('/call', APICallHandler),
    ('/callback_api', CallbackRequestHTTPHandler),
    ('/start_flow', ExecuteFlowHandler),
    ('/get_flows', ListMessageFlowRunsHandler),
    ('/get_flow_member_results', ListMessageFlowMemberResultsHandler),
    ('/mfr/(.*)', MFRHandler),
    ('/mfmr/(.*)', MFMRHandler),
    ('/mass_invite', MassInviteHandler),
    ('/get_links', ListPokeTagMessageFlowLinksHandler),
    ('/create_link', CreatePokeTagMessageFlowLinkHandler),
    ('/delete_link', DeletePokeTagLinkHandler),
    ('/channel/token', GetChannelAPITokenHandler),
    ('/mobiadmin/rest/explore/code/compile', CompileRequestHandler),
    ('/mobiadmin/rest/explore/code/run', RunCodeRequestHandler),
    ('/mobiadmin/rest/explore/code/delete', DeleteCodeRequestHandler),
    ('/mobiadmin/rest/explore/code/get', GetCodeRequestHandler),
    ('/mobiadmin/settings', ServerSettingsHandler),
    ('/mobiadmin/explorer', ExplorerPage),
    ('/mobiadmin/cron/session/cleanup', SessionCleanupHandler),
    ('/mobiadmin/cron/firebase/cleanup', FirebaseCleanupHandler),
]

app = webapp2.WSGIApplication(mapping)
