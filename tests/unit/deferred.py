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

'''Functional test for deferred.py'''

import pytest

from haas import config, deferred, model
from haas.config import cfg
from haas.model import db, Switch
from haas.test_common import config_testsuite, config_merge, \
                             fresh_database, fail_on_log_warnings


fail_on_log_warnings = pytest.fixture(autouse=True)(fail_on_log_warnings)
fresh_database = pytest.fixture(fresh_database)

INTERFACE1 = '104/0/10'
INTERFACE2 = '104/0/18'

DeferredTestSwitch = None


@pytest.fixture
def configure():
    config_testsuite()
    config_merge({
        'extensions': {
            'haas.ext.obm.mock': ''
        },
    })
    config.load_extensions()


@pytest.fixture()
def _deferred_test_switch_class():
    global DeferredTestSwitch

    class DeferredTestSwitch_(Switch):
        '''DeferredTestSwitch

        This is a switch implemented to test the deferred.apply_networking()
        function.  It is needed for a custom implementation of the switche's
        apply_networking() that counts the networking actions as
        apply_networking() is called to ensure it is incremental.
        '''

        api_name = 'http://schema.massopencloud.org/haas/v0/switches/deferred'

        __mapper_args__ = {
            'polymorphic_identity': api_name,
        }

        id = db.Column(db.Integer,
                       db.ForeignKey('switch.id'),
                       primary_key=True)
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

    DeferredTestSwitch_.__name__ = 'DeferredTestSwitch'
    DeferredTestSwitch = DeferredTestSwitch_


@pytest.fixture()
def switch(_deferred_test_switch_class):
    return DeferredTestSwitch(
        label='switch',
        hostname='http://example.com',
        username='admin',
        password='admin',
    ).session()


@pytest.fixture()
def nic1():
    from haas.ext.obm.mock import MockObm
    return model.Nic(
        model.Node(
            label='node-99',
            obm=MockObm(
                type="http://schema.massopencloud.org/haas/v0/obm/mock",
                host="ipmihost",
                user="root",
                password="tapeworm")),
        'ipmi',
        '00:11:22:33:44:55')


@pytest.fixture()
def nic2():
    from haas.ext.obm.mock import MockObm
    return model.Nic(
        model.Node(
            label='node-98',
            obm=MockObm(
                type="http://schema.massopencloud.org/haas/v0/obm/mock",
                host="ipmihost",
                user="root",
                password="tapeworm")),
        'ipmi',
        '00:11:22:33:44:55')


@pytest.fixture()
def network():
    project = model.Project('anvil-nextgen')
    return model.Network(project, [project], True, '102', 'hammernet')

pytestmark = pytest.mark.usefixtures('configure',
                                     'fail_on_log_warnings')


def test_apply_networking(switch, nic1, nic2, network, fresh_database):
    '''Test to validate apply_networking commits actions incrementally

    This test verifies that the apply_networking() function in haas/deferred.py
    incrementally commits actions, which ensures that any error on an action
    will not require a complete rerun of the prior actions (e.g. if an error
    is thrown on the 3rd action, the 1st and 2nd action will have already been
    committed)
    '''
    from haas.ext.obm.mock import MockObm

    port = model.Port(label=INTERFACE1, switch=switch)
    nic1.port = port

    port = model.Port(label=INTERFACE2, switch=switch)
    nic2.port = port

    action_native1 = model.NetworkingAction(nic=nic1,
                                            new_network=network,
                                            channel='vlan/native')
    action_native2 = model.NetworkingAction(nic=nic2,
                                            new_network=network,
                                            channel='vlan/native')

    db.session.add(action_native1)
    db.session.add(action_native2)
    db.session.commit()

    deferred.apply_networking()
