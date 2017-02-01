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


from haas import config, deferred, model
from haas.ext.obm.ipmi import Ipmi
from haas.model import db
from haas.test_common import config_testsuite, config_merge, \
                             fresh_database, fail_on_log_warnings

from sqlalchemy import Column, Integer, ForeignKey, String

fail_on_log_warnings = pytest.fixture(autouse=True)(fail_on_log_warnings)
fresh_database = pytest.fixture(fresh_database)

INTERFACE1 = '104/0/10'
INTERFACE2 = '104/0/18'


@pytest.fixture
def configure():
    config_testsuite()
    config_merge({
        'extensions': {
            'haas.ext.auth.mock': '',
            'haas.ext.auth.null': None,
        },
    })
    config.load_extensions()


@pytest.fixture()
def switch():
    return MockTestSwitch(
        label='switch',
        hostname='http://example.com',
        username='admin',
        password='admin',
    ).session()


@pytest.fixture()
def nic1():
    return model.Nic(
        model.Node(
            label='node-99',
            obm=Ipmi(
                type="http://schema.massopencloud.org/haas/v0/obm/ipmi",
                host="ipmihost",
                user="root",
                password="tapeworm")),
        'ipmi',
        '00:11:22:33:44:55')


@pytest.fixture()
def nic2():
    return model.Nic(
        model.Node(
            label='node-98',
            obm=Ipmi(
                type="http://schema.massopencloud.org/haas/v0/obm/ipmi",
                host="ipmihost",
                user="root",
                password="tapeworm")),
        'ipmi',
        '00:11:22:33:44:55')


@pytest.fixture
def network():
    project = model.Project('anvil-nextgen')
    return model.Network(project, [project], True, '102', 'hammernet')

pytestmark = pytest.mark.usefixtures('configure',
                                     'fresh_database')


def test_apply_networking(switch, nic1, nic2, network):
    # Create a port on the switch and connect it to the nic
    port = model.Port(label=INTERFACE1, switch=switch)
    nic1.port = port

    port = model.Port(label=INTERFACE2, switch=switch)
    nic2.port = port

    # Test action to set a network as native
    action_native1 = model.NetworkingAction(nic=nic1,
                                            new_network=network,
                                            channel='vlan/native')
    action_native2 = model.NetworkingAction(nic=nic2,
                                            new_network=network,
                                            channel='vlan/native')

    db.session.add(action_native1)
    db.session.add(action_native2)
    db.session.commit()

    current_count = db.session.query(model.NetworkingAction).count()
    last_count = current_count

    deferred.apply_networking()


class MockTestSwitch(model.Switch):

    api_name = 'http://schema.massopencloud.org/haas/v0/switches/mock'

    __mapper_args__ = {
        'polymorphic_identity': api_name,
    }

    id = Column(Integer, ForeignKey('switch.id'), primary_key=True)
    hostname = Column(String, nullable=False)
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)
    last_count = None

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
