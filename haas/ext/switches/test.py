# Copyright 2016 Massachusetts Open Cloud Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the
# License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS
# IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language
# governing permissions and limitations under the License.

import pytest
import schema

from collections import defaultdict
from haas.migrations import paths
from haas import model
from haas.model import db, Switch
from os.path import dirname, join

paths[__name__] = join(dirname(__file__), 'migrations', 'test')

LOCAL_STATE = defaultdict(lambda: defaultdict(dict))


class TestSwitch(Switch):

    api_name = 'http://schema.massopencloud.org/haas/v0/switches/test'

    __mapper_args__ = {
        'polymorphic_identity': api_name,
    }

    id = db.Column(db.Integer, db.ForeignKey('switch.id'), primary_key=True)
    hostname = db.Column(db.String, nullable=False)
    username = db.Column(db.String, nullable=False)
    password = db.Column(db.String, nullable=False)
    last_count = None

    @staticmethod
    def validate(kwargs):
        schema.Schema({
            'username': basestring,
            'hostname': basestring,
            'password': basestring,
        }).validate(kwargs)

    def session(self):
        return self

    def disconnect(self):
        pass

    def apply_networking(self, action):
        current_count = db.session.query(model.NetworkingAction).count()

        if self.last_count is None:
            self.last_count = current_count
        else:
            assert current_count == self.last_count - 1, \
              "network daemon did not commit previous change!"
            self.last_count = current_count
