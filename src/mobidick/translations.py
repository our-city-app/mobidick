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

import logging

__all__ = [ 'localize', 'SUPPORTED_LANGUAGES' ]

DEFAULT_LANGUAGE = "en"

def localize(lang, key, **kwargs):
    if not lang:
        lang = DEFAULT_LANGUAGE
    lang = lang.replace('-', '_')
    if lang not in D:
        if '_' in lang:
            lang = lang.split('_')[0]
            if lang not in D:
                lang = DEFAULT_LANGUAGE
        else:
            lang = DEFAULT_LANGUAGE
    langdict = D[lang]
    if key not in langdict:
        # Fall back to default language
        if lang != DEFAULT_LANGUAGE:
            logging.warn("Translation key %s not found in language %s - fallback to default" % (key, lang))
            lang = DEFAULT_LANGUAGE
            langdict = D[lang]
    if key in langdict:
        return langdict[key] % kwargs
    logging.warn("Translation key %s not found in default language. Fallback to key" % key)
    return unicode(key) % kwargs

D = { }

D["en"] = {
    "Send": "Send",
    "Cancel": "Cancel",
    "Reply": "Reply"
}

D["es"] = {
    "Send": "Enviar",
    "Cancel": "Cancelar",
    "Reply": "Responder"
}

D["fr"] = {
    "Send": "Envoyer",
    "Cancel": "Annuler",
    "Reply": "Répondre"
}

D["nl"] = {
    "Send": "Verzenden",
    "Cancel": "Annuleren",
    "Reply": "Antwoorden"
}


# Keep this line at the bottom
SUPPORTED_LANGUAGES = D.keys()
