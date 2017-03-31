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
# @@license_version:1.2@@

import time

from google.appengine.ext import webapp


def datestring(timestamp):
    return time.ctime(timestamp)

def escape_csv(value):
    return unicode(value).replace('"', '""')

def form_result(value):
    if not (value and value.get("form_result") and value["form_result"].get("result")):
        return u""
    value = value["form_result"]
    if value["type"] in ("unicode_result", "long_result"):
        return unicode(value["result"]["value"])
    if value["type"] == "float_result":
        return unicode(value["result"]["value"]).replace(".", ",")
    if value["type"] == "float_list_result":
        return u";".join((unicode(v).replace(".", ",") for v in value["result"]["values"]))
    else:
        return u";".join((unicode(v) for v in value["result"]["values"]))

def answer_id(value):
    if not value:
        return "Roger that!"
    else:
        return value

register = webapp.template.create_template_register()
register.filter('datestring', datestring)
register.filter('escape_csv', escape_csv)
register.filter('form_result', form_result)
register.filter('answer_id', answer_id)
