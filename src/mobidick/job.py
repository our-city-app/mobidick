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

import inspect

from google.appengine.ext import deferred, db
from mobidick.utils import azzert


HIGH_LOAD_CONTROLLER_QUEUE = "highload-controller-queue"
HIGH_LOAD_WORKER_QUEUE = "highload-worker-queue"


BATCH_SIZE = 20
MODE_SINGLE = 1
MODE_BATCH = 2

def run_job(qry_function, qry_function_args, worker_function, worker_function_args, mode=MODE_SINGLE, \
            batch_size=BATCH_SIZE, batch_timeout=0, qry_transactional=False):
    """Executes a function for each item in the resultset in the query delivered by the qry_function and qry_function_args.
    The qry_function should only return keys."""
    azzert(inspect.isfunction(qry_function), "Only functions allowed")
    azzert(isinstance(qry_function_args, list))
    azzert(inspect.isfunction(worker_function), "Only functions allowed")
    azzert(isinstance(worker_function_args, list))
    azzert(mode in (MODE_SINGLE, MODE_BATCH))
    deferred.defer(_run_qry, qry_function, qry_function_args, worker_function, worker_function_args, \
                   mode, batch_size, batch_timeout, qry_transactional=qry_transactional, _transactional=db.is_in_transaction(), \
                   _queue=HIGH_LOAD_CONTROLLER_QUEUE)

def _run_qry(qry_function, qry_function_args, worker_function, worker_function_args, mode, batch_size, batch_timeout,
             batch_timeout_counter=0, cursor=None, qry_transactional=False):
    def trans1():
        qry = qry_function(*qry_function_args)
        qry.with_cursor(cursor)
        items = qry.fetch(batch_size * 4)
        return items, qry
    items, qry = db.run_in_transaction(trans1) if qry_transactional else trans1()
    if not items:
        return

    def trans2(items):
        # Take copy because db.run_in_transaction might execute this method a number of times in
        # case of transaction collisions
        items = list(items)
        count_down = batch_timeout_counter
        while items:
            if mode == MODE_SINGLE:
                deferred.defer(_run_batch, items[:batch_size], worker_function, worker_function_args, \
                               _transactional=True, _queue=HIGH_LOAD_CONTROLLER_QUEUE, _countdown=count_down)
            else:
                deferred.defer(worker_function, items[:batch_size], *worker_function_args, \
                               _transactional=True, _queue=HIGH_LOAD_WORKER_QUEUE, _countdown=count_down)
            count_down += batch_timeout
            items = items[batch_size:]
        deferred.defer(_run_qry, qry_function, qry_function_args, worker_function, worker_function_args, mode, \
                       batch_size, batch_timeout, count_down, qry.cursor(), qry_transactional, \
                       _transactional=True, _queue=HIGH_LOAD_CONTROLLER_QUEUE)
    db.run_in_transaction(trans2, items)

def _run_batch(items, worker_function, worker_function_args):
    def trans(items):
        # Take copy because db.run_in_transaction might execute this method a number of times in
        # case of transaction collisions
        items = list(items)
        try:
            for _ in xrange(4):
                item = items.pop()
                deferred.defer(worker_function, item, *worker_function_args, _transactional=True, \
                               _queue=HIGH_LOAD_WORKER_QUEUE)
            deferred.defer(_run_batch, items, worker_function, worker_function_args, \
                           _transactional=True, _queue=HIGH_LOAD_CONTROLLER_QUEUE)
        except IndexError:
            pass
    db.run_in_transaction(trans, items)
