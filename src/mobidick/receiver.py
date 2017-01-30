# -*- coding: utf-8 -*-
# Copyright 2017 Mobicage NV
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
# @@license_version:1.2@@

import json

from mobidick.business import call
import webapp2


MOBIDICK_SIK = "02e14d53ff44a0d10c7894111b21ac1d6b3d23592ff59564dbac312cd7797c5f"

class CallbackRequestHTTPHandler(webapp2.RequestHandler):

    def post(self):
        # VALIDATE THE INCOMING REQUEST
        # assert self.request.headers.get("X-Nuntiuz-Service-Key", None) == MOBIDICK_SIK
        sik = self.request.headers.get("X-Nuntiuz-Service-Key", None)
        assert sik

        # PARSE THE JSON-RPC CALL
        call_json = json.loads(self.request.body)

        # PERFORM CALL
        response = call(call_json, sik)

        # WIRE RESULT
        self.response.headers['Content-Type'] = 'application/json-rpc'
        json.dump(response, self.response.out)
