# -*- encoding: utf-8 -*-
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
"""
Tests for the API /portgroups/ methods.
"""

import datetime

import mock
from oslo_config import cfg
from oslo_utils import timeutils
from oslo_utils import uuidutils
import six
from six.moves import http_client
from six.moves.urllib import parse as urlparse
from testtools.matchers import HasLength
from wsme import types as wtypes

from ironic.api.controllers import base as api_base
from ironic.api.controllers import v1 as api_v1
from ironic.api.controllers.v1 import portgroup as api_portgroup
from ironic.api.controllers.v1 import utils as api_utils
from ironic.common import exception
from ironic.conductor import rpcapi
from ironic.tests import base
from ironic.tests.unit.api import base as test_api_base
from ironic.tests.unit.api import utils as apiutils
from ironic.tests.unit.db import utils as dbutils
from ironic.tests.unit.objects import utils as obj_utils


# NOTE: When creating a portgroup via API (POST)
#       we have to use node_uuid
def post_get_test_portgroup(**kw):
    portgroup = apiutils.portgroup_post_data(**kw)
    node = dbutils.get_test_node()
    del portgroup['node_id']
    portgroup['node_uuid'] = kw.get('node_uuid', node['uuid'])
    return portgroup


class TestPortgroupObject(base.TestCase):

    def test_portgroup_init(self):
        portgroup_dict = apiutils.portgroup_post_data(node_id=None)
        del portgroup_dict['extra']
        portgroup = api_portgroup.Portgroup(**portgroup_dict)
        self.assertEqual(wtypes.Unset, portgroup.extra)


class TestListPortgroups(test_api_base.BaseApiTest):

    def setUp(self):
        super(TestListPortgroups, self).setUp()
        self.node = obj_utils.create_test_node(self.context)

    def test_empty(self):
        data = self.get_json('/portgroups')
        self.assertEqual([], data['portgroups'])

    def test_one(self):
        portgroup = obj_utils.create_test_portgroup(self.context,
                                                    node_id=self.node.id)
        data = self.get_json('/portgroups')
        self.assertEqual(portgroup.uuid, data['portgroups'][0]["uuid"])
        self.assertNotIn('extra', data['portgroups'][0])
        self.assertNotIn('node_uuid', data['portgroups'][0])
        # never expose the node_id
        self.assertNotIn('node_id', data['portgroups'][0])

    def test_get_one(self):
        portgroup = obj_utils.create_test_portgroup(self.context,
                                                    node_id=self.node.id)
        data = self.get_json('/portgroups/%s' % portgroup.uuid)
        self.assertEqual(portgroup.uuid, data['uuid'])
        self.assertIn('extra', data)
        self.assertIn('node_uuid', data)
        # never expose the node_id
        self.assertNotIn('node_id', data)

    def test_get_one_custom_fields(self):
        portgroup = obj_utils.create_test_portgroup(self.context,
                                                    node_id=self.node.id)
        fields = 'address,extra'
        data = self.get_json(
            '/portgroups/%s?fields=%s' % (portgroup.uuid, fields),
            headers={api_base.Version.string: str(api_v1.MAX_VER)})
        # We always append "links"
        self.assertItemsEqual(['address', 'extra', 'links'], data)

    def test_get_collection_custom_fields(self):
        fields = 'uuid,extra'
        for i in range(3):
            obj_utils.create_test_portgroup(
                self.context,
                node_id=self.node.id,
                uuid=uuidutils.generate_uuid(),
                name=str(uuidutils.generate_uuid()),
                address='52:54:00:cf:2d:3%s' % i)

        data = self.get_json(
            '/portgroups?fields=%s' % fields,
            headers={api_base.Version.string: str(api_v1.MAX_VER)})

        self.assertEqual(3, len(data['portgroups']))
        for portgroup in data['portgroups']:
            # We always append "links"
            self.assertItemsEqual(['uuid', 'extra', 'links'], portgroup)

    def test_get_custom_fields_invalid_fields(self):
        portgroup = obj_utils.create_test_portgroup(self.context,
                                                    node_id=self.node.id)
        fields = 'uuid,spongebob'
        response = self.get_json(
            '/portgroups/%s?fields=%s' % (portgroup.uuid, fields),
            headers={api_base.Version.string: str(api_v1.MAX_VER)},
            expect_errors=True)
        self.assertEqual(http_client.BAD_REQUEST, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertIn('spongebob', response.json['error_message'])

    def test_get_custom_fields_invalid_api_version(self):
        portgroup = obj_utils.create_test_portgroup(self.context,
                                                    node_id=self.node.id)
        fields = 'uuid,extra'
        response = self.get_json(
            '/portgroups/%s?fields=%s' % (portgroup.uuid, fields),
            headers={api_base.Version.string: str(api_v1.MIN_VER)},
            expect_errors=True)
        self.assertEqual(http_client.NOT_ACCEPTABLE, response.status_int)

    def test_detail(self):
        portgroup = obj_utils.create_test_portgroup(self.context,
                                                    node_id=self.node.id)
        data = self.get_json('/portgroups/detail')
        self.assertEqual(portgroup.uuid, data['portgroups'][0]["uuid"])
        self.assertIn('extra', data['portgroups'][0])
        self.assertIn('node_uuid', data['portgroups'][0])
        # never expose the node_id
        self.assertNotIn('node_id', data['portgroups'][0])

    def test_detail_against_single(self):
        portgroup = obj_utils.create_test_portgroup(self.context,
                                                    node_id=self.node.id)
        response = self.get_json('/portgroups/%s/detail' % portgroup.uuid,
                                 expect_errors=True)
        self.assertEqual(http_client.NOT_FOUND, response.status_int)

    def test_many(self):
        portgroups = []
        for id_ in range(5):
            portgroup = obj_utils.create_test_portgroup(
                self.context, node_id=self.node.id,
                uuid=uuidutils.generate_uuid(),
                name=str(uuidutils.generate_uuid()),
                address='52:54:00:cf:2d:3%s' % id_)
            portgroups.append(portgroup.uuid)
        data = self.get_json('/portgroups')
        self.assertEqual(len(portgroups), len(data['portgroups']))

        uuids = [n['uuid'] for n in data['portgroups']]
        six.assertCountEqual(self, portgroups, uuids)

    def test_links(self):
        uuid = uuidutils.generate_uuid()
        obj_utils.create_test_portgroup(self.context,
                                        uuid=uuid,
                                        node_id=self.node.id)
        data = self.get_json('/portgroups/%s' % uuid)
        self.assertIn('links', data.keys())
        self.assertEqual(2, len(data['links']))
        self.assertIn(uuid, data['links'][0]['href'])
        for l in data['links']:
            bookmark = l['rel'] == 'bookmark'
            self.assertTrue(self.validate_link(l['href'], bookmark=bookmark))

    def test_collection_links(self):
        portgroups = []
        for id_ in range(5):
            portgroup = obj_utils.create_test_portgroup(
                self.context,
                node_id=self.node.id,
                uuid=uuidutils.generate_uuid(),
                name=str(uuidutils.generate_uuid()),
                address='52:54:00:cf:2d:3%s' % id_)
            portgroups.append(portgroup.uuid)
        data = self.get_json('/portgroups/?limit=3')
        self.assertEqual(3, len(data['portgroups']))

        next_marker = data['portgroups'][-1]['uuid']
        self.assertIn(next_marker, data['next'])

    def test_collection_links_default_limit(self):
        cfg.CONF.set_override('max_limit', 3, 'api')
        portgroups = []
        for id_ in range(5):
            portgroup = obj_utils.create_test_portgroup(
                self.context,
                node_id=self.node.id,
                uuid=uuidutils.generate_uuid(),
                name=str(uuidutils.generate_uuid()),
                address='52:54:00:cf:2d:3%s' % id_)
            portgroups.append(portgroup.uuid)
        data = self.get_json('/portgroups')
        self.assertEqual(3, len(data['portgroups']))

        next_marker = data['portgroups'][-1]['uuid']
        self.assertIn(next_marker, data['next'])

    def test_portgroup_by_address(self):
        address_template = "aa:bb:cc:dd:ee:f%d"
        for id_ in range(3):
            obj_utils.create_test_portgroup(
                self.context,
                node_id=self.node.id,
                uuid=uuidutils.generate_uuid(),
                name=str(uuidutils.generate_uuid()),
                address=address_template % id_)

        target_address = address_template % 1
        data = self.get_json('/portgroups?address=%s' % target_address)
        self.assertThat(data['portgroups'], HasLength(1))
        self.assertEqual(target_address, data['portgroups'][0]['address'])

    def test_portgroup_by_address_non_existent_address(self):
        # non-existent address
        data = self.get_json('/portgroups?address=%s' % 'aa:bb:cc:dd:ee:ff')
        self.assertThat(data['portgroups'], HasLength(0))

    def test_portgroup_by_address_invalid_address_format(self):
        obj_utils.create_test_portgroup(self.context, node_id=self.node.id)
        invalid_address = 'invalid-mac-format'
        response = self.get_json('/portgroups?address=%s' % invalid_address,
                                 expect_errors=True)
        self.assertEqual(http_client.BAD_REQUEST, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertIn(invalid_address, response.json['error_message'])

    def test_sort_key(self):
        portgroups = []
        for id_ in range(3):
            portgroup = obj_utils.create_test_portgroup(
                self.context,
                node_id=self.node.id,
                uuid=uuidutils.generate_uuid(),
                name=str(uuidutils.generate_uuid()),
                address='52:54:00:cf:2d:3%s' % id_)
            portgroups.append(portgroup.uuid)
        data = self.get_json('/portgroups?sort_key=uuid')
        uuids = [n['uuid'] for n in data['portgroups']]
        self.assertEqual(sorted(portgroups), uuids)

    def test_sort_key_invalid(self):
        invalid_keys_list = ['foo', 'extra']
        for invalid_key in invalid_keys_list:
            response = self.get_json('/portgroups?sort_key=%s' % invalid_key,
                                     expect_errors=True)
            self.assertEqual(http_client.BAD_REQUEST, response.status_int)
            self.assertEqual('application/json', response.content_type)
            self.assertIn(invalid_key, response.json['error_message'])

    @mock.patch.object(api_utils, 'get_rpc_node')
    def test_get_all_by_node_name_ok(self, mock_get_rpc_node):
        # GET /v1/portgroups specifying node_name - success
        mock_get_rpc_node.return_value = self.node
        for i in range(5):
            if i < 3:
                node_id = self.node.id
            else:
                node_id = 100000 + i
            obj_utils.create_test_portgroup(
                self.context,
                node_id=node_id,
                uuid=uuidutils.generate_uuid(),
                name=str(uuidutils.generate_uuid()),
                address='52:54:00:cf:2d:3%s' % i)
        data = self.get_json("/portgroups?node=%s" % 'test-node',
                             headers={api_base.Version.string: '1.5'})
        self.assertEqual(3, len(data['portgroups']))

    @mock.patch.object(api_utils, 'get_rpc_node')
    def test_get_all_by_node_uuid_and_name(self, mock_get_rpc_node):
        # GET /v1/portgroups specifying node and uuid - should only use
        # node_uuid
        mock_get_rpc_node.return_value = self.node
        obj_utils.create_test_portgroup(self.context, node_id=self.node.id)
        self.get_json('/portgroups/detail?node_uuid=%s&node=%s' %
                      (self.node.uuid, 'node-name'))
        mock_get_rpc_node.assert_called_once_with(self.node.uuid)

    @mock.patch.object(api_utils, 'get_rpc_node')
    def test_get_all_by_node_name_not_supportgrouped(self, mock_get_rpc_node):
        # GET /v1/portgroups specifying node_name - name not supportgrouped
        mock_get_rpc_node.side_effect = (
            exception.InvalidUuidOrName(name=self.node.uuid))
        for i in range(3):
            obj_utils.create_test_portgroup(
                self.context,
                node_id=self.node.id,
                uuid=uuidutils.generate_uuid(),
                name=str(uuidutils.generate_uuid()),
                address='52:54:00:cf:2d:3%s' % i)
        data = self.get_json("/portgroups?node=%s" % 'test-node',
                             expect_errors=True)
        self.assertEqual(0, mock_get_rpc_node.call_count)
        self.assertEqual(http_client.NOT_ACCEPTABLE, data.status_int)

    @mock.patch.object(api_utils, 'get_rpc_node')
    def test_detail_by_node_name_ok(self, mock_get_rpc_node):
        # GET /v1/portgroups/detail specifying node_name - success
        mock_get_rpc_node.return_value = self.node
        portgroup = obj_utils.create_test_portgroup(self.context,
                                                    node_id=self.node.id)
        data = self.get_json('/portgroups/detail?node=%s' % 'test-node',
                             headers={api_base.Version.string: '1.5'})
        self.assertEqual(portgroup.uuid, data['portgroups'][0]['uuid'])
        self.assertEqual(self.node.uuid, data['portgroups'][0]['node_uuid'])

    @mock.patch.object(api_utils, 'get_rpc_node')
    def test_detail_by_node_name_not_supportgrouped(self, mock_get_rpc_node):
        # GET /v1/portgroups/detail specifying node_name - name not supported
        mock_get_rpc_node.side_effect = (
            exception.InvalidUuidOrName(name=self.node.uuid))
        obj_utils.create_test_portgroup(self.context, node_id=self.node.id)
        data = self.get_json('/portgroups/detail?node=%s' % 'test-node',
                             expect_errors=True)
        self.assertEqual(0, mock_get_rpc_node.call_count)
        self.assertEqual(http_client.NOT_ACCEPTABLE, data.status_int)

    @mock.patch.object(api_portgroup.PortgroupsController,
                       '_get_portgroups_collection')
    def test_detail_with_incorrect_api_usage(self, mock_gpc):
        # GET /v1/portgroups/detail specifying node and node_uuid.
        # In this case we expect the node_uuid interface to be used.
        self.get_json('/portgroups/detail?node=%s&node_uuid=%s' %
                      ('test-node', self.node.uuid))
        mock_gpc.assert_called_once_with(self.node.uuid, mock.ANY, mock.ANY,
                                         mock.ANY, mock.ANY, mock.ANY,
                                         mock.ANY)


@mock.patch.object(rpcapi.ConductorAPI, 'update_portgroup')
class TestPatch(test_api_base.BaseApiTest):

    def setUp(self):
        super(TestPatch, self).setUp()
        self.node = obj_utils.create_test_node(self.context)
        self.portgroup = obj_utils.create_test_portgroup(self.context,
                                                         node_id=self.node.id)

        p = mock.patch.object(rpcapi.ConductorAPI, 'get_topic_for')
        self.mock_gtf = p.start()
        self.mock_gtf.return_value = 'test-topic'
        self.addCleanup(p.stop)

    def test_update_byid(self, mock_upd):
        extra = {'foo': 'bar'}
        mock_upd.return_value = self.portgroup
        mock_upd.return_value.extra = extra
        response = self.patch_json('/portgroups/%s' % self.portgroup.uuid,
                                   [{'path': '/extra/foo',
                                     'value': 'bar',
                                     'op': 'add'}])
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.OK, response.status_code)
        self.assertEqual(extra, response.json['extra'])

        kargs = mock_upd.call_args[0][1]
        self.assertEqual(extra, kargs.extra)

    def test_update_byaddress_not_allowed(self, mock_upd):
        extra = {'foo': 'bar'}
        mock_upd.return_value = self.portgroup
        mock_upd.return_value.extra = extra
        response = self.patch_json('/portgroups/%s' % self.portgroup.address,
                                   [{'path': '/extra/foo',
                                     'value': 'bar',
                                     'op': 'add'}],
                                   expect_errors=True)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.BAD_REQUEST, response.status_int)
        self.assertIn(self.portgroup.address, response.json['error_message'])
        self.assertFalse(mock_upd.called)

    def test_update_not_found(self, mock_upd):
        uuid = uuidutils.generate_uuid()
        response = self.patch_json('/portgroups/%s' % uuid,
                                   [{'path': '/extra/foo',
                                     'value': 'bar',
                                     'op': 'add'}],
                                   expect_errors=True)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.NOT_FOUND, response.status_int)
        self.assertTrue(response.json['error_message'])
        self.assertFalse(mock_upd.called)

    def test_replace_singular(self, mock_upd):
        address = 'aa:bb:cc:dd:ee:ff'
        mock_upd.return_value = self.portgroup
        mock_upd.return_value.address = address
        response = self.patch_json('/portgroups/%s' % self.portgroup.uuid,
                                   [{'path': '/address',
                                     'value': address,
                                     'op': 'replace'}])
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.OK, response.status_code)
        self.assertEqual(address, response.json['address'])
        self.assertTrue(mock_upd.called)

        kargs = mock_upd.call_args[0][1]
        self.assertEqual(address, kargs.address)

    def test_replace_address_already_exist(self, mock_upd):
        address = 'aa:aa:aa:aa:aa:aa'
        mock_upd.side_effect = exception.MACAlreadyExists(mac=address)
        response = self.patch_json('/portgroups/%s' % self.portgroup.uuid,
                                   [{'path': '/address',
                                     'value': address,
                                     'op': 'replace'}],
                                   expect_errors=True)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.CONFLICT, response.status_code)
        self.assertTrue(response.json['error_message'])
        self.assertTrue(mock_upd.called)

        kargs = mock_upd.call_args[0][1]
        self.assertEqual(address, kargs.address)

    def test_replace_node_uuid(self, mock_upd):
        mock_upd.return_value = self.portgroup
        response = self.patch_json('/portgroups/%s' % self.portgroup.uuid,
                                   [{'path': '/node_uuid',
                                     'value': self.node.uuid,
                                     'op': 'replace'}])
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.OK, response.status_code)

    def test_add_node_uuid(self, mock_upd):
        mock_upd.return_value = self.portgroup
        response = self.patch_json('/portgroups/%s' % self.portgroup.uuid,
                                   [{'path': '/node_uuid',
                                     'value': self.node.uuid,
                                     'op': 'add'}])
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.OK, response.status_code)

    def test_add_node_id(self, mock_upd):
        response = self.patch_json('/portgroups/%s' % self.portgroup.uuid,
                                   [{'path': '/node_id',
                                     'value': '1',
                                     'op': 'add'}],
                                   expect_errors=True)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.BAD_REQUEST, response.status_code)
        self.assertFalse(mock_upd.called)

    def test_replace_node_id(self, mock_upd):
        response = self.patch_json('/portgroups/%s' % self.portgroup.uuid,
                                   [{'path': '/node_id',
                                     'value': '1',
                                     'op': 'replace'}],
                                   expect_errors=True)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.BAD_REQUEST, response.status_code)
        self.assertFalse(mock_upd.called)

    def test_remove_node_id(self, mock_upd):
        response = self.patch_json('/portgroups/%s' % self.portgroup.uuid,
                                   [{'path': '/node_id',
                                     'op': 'remove'}],
                                   expect_errors=True)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.BAD_REQUEST, response.status_code)
        self.assertFalse(mock_upd.called)

    def test_replace_non_existent_node_uuid(self, mock_upd):
        node_uuid = '12506333-a81c-4d59-9987-889ed5f8687b'
        response = self.patch_json('/portgroups/%s' % self.portgroup.uuid,
                                   [{'path': '/node_uuid',
                                     'value': node_uuid,
                                     'op': 'replace'}],
                                   expect_errors=True)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.BAD_REQUEST, response.status_code)
        self.assertIn(node_uuid, response.json['error_message'])
        self.assertFalse(mock_upd.called)

    def test_replace_multi(self, mock_upd):
        extra = {"foo1": "bar1", "foo2": "bar2", "foo3": "bar3"}
        self.portgroup.extra = extra
        self.portgroup.save()

        # mutate extra so we replace all of them
        extra = dict((k, extra[k] + 'x') for k in extra.keys())

        patch = []
        for k in extra.keys():
            patch.append({'path': '/extra/%s' % k,
                          'value': extra[k],
                          'op': 'replace'})
        mock_upd.return_value = self.portgroup
        mock_upd.return_value.extra = extra
        response = self.patch_json('/portgroups/%s' % self.portgroup.uuid,
                                   patch)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.OK, response.status_code)
        self.assertEqual(extra, response.json['extra'])
        kargs = mock_upd.call_args[0][1]
        self.assertEqual(extra, kargs.extra)

    def test_remove_multi(self, mock_upd):
        extra = {"foo1": "bar1", "foo2": "bar2", "foo3": "bar3"}
        self.portgroup.extra = extra
        self.portgroup.save()

        # Removing one item from the collection
        extra.pop('foo1')
        mock_upd.return_value = self.portgroup
        mock_upd.return_value.extra = extra
        response = self.patch_json('/portgroups/%s' % self.portgroup.uuid,
                                   [{'path': '/extra/foo1',
                                     'op': 'remove'}])
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.OK, response.status_code)
        self.assertEqual(extra, response.json['extra'])
        kargs = mock_upd.call_args[0][1]
        self.assertEqual(extra, kargs.extra)

        # Removing the collection
        extra = {}
        mock_upd.return_value.extra = extra
        response = self.patch_json('/portgroups/%s' % self.portgroup.uuid,
                                   [{'path': '/extra', 'op': 'remove'}])
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.OK, response.status_code)
        self.assertEqual({}, response.json['extra'])
        kargs = mock_upd.call_args[0][1]
        self.assertEqual(extra, kargs.extra)

        # Assert nothing else was changed
        self.assertEqual(self.portgroup.uuid, response.json['uuid'])
        self.assertEqual(self.portgroup.address, response.json['address'])

    def test_remove_non_existent_property_fail(self, mock_upd):
        response = self.patch_json('/portgroups/%s' % self.portgroup.uuid,
                                   [{'path': '/extra/non-existent',
                                     'op': 'remove'}],
                                   expect_errors=True)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.BAD_REQUEST, response.status_code)
        self.assertTrue(response.json['error_message'])
        self.assertFalse(mock_upd.called)

    def test_remove_mandatory_field(self, mock_upd):
        response = self.patch_json('/portgroups/%s' % self.portgroup.uuid,
                                   [{'path': '/address',
                                     'op': 'remove'}],
                                   expect_errors=True)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.BAD_REQUEST, response.status_code)
        self.assertTrue(response.json['error_message'])
        self.assertFalse(mock_upd.called)

    def test_add_root(self, mock_upd):
        address = 'aa:bb:cc:dd:ee:ff'
        mock_upd.return_value = self.portgroup
        mock_upd.return_value.address = address
        response = self.patch_json('/portgroups/%s' % self.portgroup.uuid,
                                   [{'path': '/address',
                                     'value': address,
                                     'op': 'add'}])
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.OK, response.status_code)
        self.assertEqual(address, response.json['address'])
        self.assertTrue(mock_upd.called)
        kargs = mock_upd.call_args[0][1]
        self.assertEqual(address, kargs.address)

    def test_add_root_non_existent(self, mock_upd):
        response = self.patch_json('/portgroups/%s' % self.portgroup.uuid,
                                   [{'path': '/foo',
                                     'value': 'bar',
                                     'op': 'add'}],
                                   expect_errors=True)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.BAD_REQUEST, response.status_int)
        self.assertTrue(response.json['error_message'])
        self.assertFalse(mock_upd.called)

    def test_add_multi(self, mock_upd):
        extra = {"foo1": "bar1", "foo2": "bar2", "foo3": "bar3"}
        patch = []
        for k in extra.keys():
            patch.append({'path': '/extra/%s' % k,
                          'value': extra[k],
                          'op': 'add'})
        mock_upd.return_value = self.portgroup
        mock_upd.return_value.extra = extra
        response = self.patch_json('/portgroups/%s' % self.portgroup.uuid,
                                   patch)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.OK, response.status_code)
        self.assertEqual(extra, response.json['extra'])
        kargs = mock_upd.call_args[0][1]
        self.assertEqual(extra, kargs.extra)

    def test_remove_uuid(self, mock_upd):
        response = self.patch_json('/portgroups/%s' % self.portgroup.uuid,
                                   [{'path': '/uuid',
                                     'op': 'remove'}],
                                   expect_errors=True)
        self.assertEqual(http_client.BAD_REQUEST, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertTrue(response.json['error_message'])
        self.assertFalse(mock_upd.called)

    def test_update_address_invalid_format(self, mock_upd):
        response = self.patch_json('/portgroups/%s' % self.portgroup.uuid,
                                   [{'path': '/address',
                                     'value': 'invalid-format',
                                     'op': 'replace'}],
                                   expect_errors=True)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.BAD_REQUEST, response.status_int)
        self.assertTrue(response.json['error_message'])
        self.assertFalse(mock_upd.called)

    def test_update_portgroup_address_normalized(self, mock_upd):
        address = 'AA:BB:CC:DD:EE:FF'
        mock_upd.return_value = self.portgroup
        mock_upd.return_value.address = address.lower()
        response = self.patch_json('/portgroups/%s' % self.portgroup.uuid,
                                   [{'path': '/address',
                                     'value': address,
                                     'op': 'replace'}])
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.OK, response.status_code)
        self.assertEqual(address.lower(), response.json['address'])
        kargs = mock_upd.call_args[0][1]
        self.assertEqual(address.lower(), kargs.address)


class TestPost(test_api_base.BaseApiTest):

    def setUp(self):
        super(TestPost, self).setUp()
        self.node = obj_utils.create_test_node(self.context)

    @mock.patch.object(timeutils, 'utcnow')
    def test_create_portgroup(self, mock_utcnow):
        pdict = post_get_test_portgroup()
        test_time = datetime.datetime(2000, 1, 1, 0, 0)
        mock_utcnow.return_value = test_time
        response = self.post_json('/portgroups', pdict)
        self.assertEqual(http_client.CREATED, response.status_int)
        result = self.get_json('/portgroups/%s' % pdict['uuid'])
        self.assertEqual(pdict['uuid'], result['uuid'])
        self.assertFalse(result['updated_at'])
        return_created_at = timeutils.parse_isotime(
            result['created_at']).replace(tzinfo=None)
        self.assertEqual(test_time, return_created_at)
        # Check location header
        self.assertIsNotNone(response.location)
        expected_location = '/v1/portgroups/%s' % pdict['uuid']
        self.assertEqual(urlparse.urlparse(response.location).path,
                         expected_location)

    def test_create_portgroup_doesnt_contain_id(self):
        with mock.patch.object(self.dbapi, 'create_portgroup',
                               wraps=self.dbapi.create_portgroup) as cp_mock:
            pdict = post_get_test_portgroup(extra={'foo': 123})
            self.post_json('/portgroups', pdict)
            result = self.get_json('/portgroups/%s' % pdict['uuid'])
            self.assertEqual(pdict['extra'], result['extra'])
            cp_mock.assert_called_once_with(mock.ANY)
            # Check that 'id' is not in first arg of positional args
            self.assertNotIn('id', cp_mock.call_args[0][0])

    def test_create_portgroup_generate_uuid(self):
        pdict = post_get_test_portgroup()
        del pdict['uuid']
        response = self.post_json('/portgroups', pdict)
        result = self.get_json('/portgroups/%s' % response.json['uuid'])
        self.assertEqual(pdict['address'], result['address'])
        self.assertTrue(uuidutils.is_uuid_like(result['uuid']))

    def test_create_portgroup_valid_extra(self):
        pdict = post_get_test_portgroup(extra={'str': 'foo', 'int': 123,
                                               'float': 0.1, 'bool': True,
                                               'list': [1, 2], 'none': None,
                                               'dict': {'cat': 'meow'}})
        self.post_json('/portgroups', pdict)
        result = self.get_json('/portgroups/%s' % pdict['uuid'])
        self.assertEqual(pdict['extra'], result['extra'])

    def test_create_portgroup_no_mandatory_field_address(self):
        pdict = post_get_test_portgroup()
        del pdict['address']
        response = self.post_json('/portgroups', pdict, expect_errors=True)
        self.assertEqual(http_client.BAD_REQUEST, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertTrue(response.json['error_message'])

    def test_create_portgroup_no_mandatory_field_node_uuid(self):
        pdict = post_get_test_portgroup()
        del pdict['node_uuid']
        response = self.post_json('/portgroups', pdict, expect_errors=True)
        self.assertEqual(http_client.BAD_REQUEST, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertTrue(response.json['error_message'])

    def test_create_portgroup_invalid_addr_format(self):
        pdict = post_get_test_portgroup(address='invalid-format')
        response = self.post_json('/portgroups', pdict, expect_errors=True)
        self.assertEqual(http_client.BAD_REQUEST, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertTrue(response.json['error_message'])

    def test_create_portgroup_address_normalized(self):
        address = 'AA:BB:CC:DD:EE:FF'
        pdict = post_get_test_portgroup(address=address)
        self.post_json('/portgroups', pdict)
        result = self.get_json('/portgroups/%s' % pdict['uuid'])
        self.assertEqual(address.lower(), result['address'])

    def test_create_portgroup_with_hyphens_delimiter(self):
        pdict = post_get_test_portgroup()
        colonsMAC = pdict['address']
        hyphensMAC = colonsMAC.replace(':', '-')
        pdict['address'] = hyphensMAC
        response = self.post_json('/portgroups', pdict, expect_errors=True)
        self.assertEqual(http_client.BAD_REQUEST, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertTrue(response.json['error_message'])

    def test_create_portgroup_invalid_node_uuid_format(self):
        pdict = post_get_test_portgroup(node_uuid='invalid-format')
        response = self.post_json('/portgroups', pdict, expect_errors=True)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.BAD_REQUEST, response.status_int)
        self.assertTrue(response.json['error_message'])

    def test_node_uuid_to_node_id_mapping(self):
        pdict = post_get_test_portgroup(node_uuid=self.node['uuid'])
        self.post_json('/portgroups', pdict)
        # GET doesn't return the node_id it's an internal value
        portgroup = self.dbapi.get_portgroup_by_uuid(pdict['uuid'])
        self.assertEqual(self.node['id'], portgroup.node_id)

    def test_create_portgroup_node_uuid_not_found(self):
        pdict = post_get_test_portgroup(
            node_uuid='1a1a1a1a-2b2b-3c3c-4d4d-5e5e5e5e5e5e')
        response = self.post_json('/portgroups', pdict, expect_errors=True)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(http_client.BAD_REQUEST, response.status_int)
        self.assertTrue(response.json['error_message'])

    def test_create_portgroup_address_already_exist(self):
        address = 'AA:AA:AA:11:22:33'
        pdict = post_get_test_portgroup(address=address)
        self.post_json('/portgroups', pdict)
        pdict['uuid'] = uuidutils.generate_uuid()
        pdict['name'] = str(uuidutils.generate_uuid())
        response = self.post_json('/portgroups', pdict, expect_errors=True)
        self.assertEqual(http_client.CONFLICT, response.status_int)
        self.assertEqual('application/json', response.content_type)
        error_msg = response.json['error_message']
        self.assertTrue(error_msg)
        self.assertIn(address, error_msg.upper())


@mock.patch.object(rpcapi.ConductorAPI, 'destroy_portgroup')
class TestDelete(test_api_base.BaseApiTest):

    def setUp(self):
        super(TestDelete, self).setUp()
        self.node = obj_utils.create_test_node(self.context)
        self.portgroup = obj_utils.create_test_portgroup(self.context,
                                                         node_id=self.node.id)

        gtf = mock.patch.object(rpcapi.ConductorAPI, 'get_topic_for')
        self.mock_gtf = gtf.start()
        self.mock_gtf.return_value = 'test-topic'
        self.addCleanup(gtf.stop)

    def test_delete_portgroup_byaddress(self, mock_dpt):
        response = self.delete('/portgroups/%s' % self.portgroup.address,
                               expect_errors=True)
        self.assertEqual(http_client.BAD_REQUEST, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertIn(self.portgroup.address, response.json['error_message'])

    def test_delete_portgroup_byid(self, mock_dpt):
        self.delete('/portgroups/%s' % self.portgroup.uuid, expect_errors=True)
        self.assertTrue(mock_dpt.called)

    def test_delete_portgroup_node_locked(self, mock_dpt):
        self.node.reserve(self.context, 'fake', self.node.uuid)
        mock_dpt.side_effect = exception.NodeLocked(node='fake-node',
                                                    host='fake-host')
        ret = self.delete('/portgroups/%s' % self.portgroup.uuid,
                          expect_errors=True)
        self.assertEqual(http_client.CONFLICT, ret.status_code)
        self.assertTrue(ret.json['error_message'])
        self.assertTrue(mock_dpt.called)
