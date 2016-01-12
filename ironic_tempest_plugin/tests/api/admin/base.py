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

import functools
import inspect

from tempest.common import api_version_utils
from tempest.common import credentials_factory as common_creds
from tempest.common import dynamic_creds
from tempest import config
from tempest import test
from tempest_lib.common.utils import data_utils
from tempest_lib import exceptions as lib_exc

from ironic_tempest_plugin import clients

CONF = config.CONF


# NOTE(adam_g): The baremetal API tests exercise operations such as enroll
# node, power on, power off, etc.  Testing against real drivers (ie, IPMI)
# will require passing driver-specific data to Tempest (addresses,
# credentials, etc).  Until then, only support testing against the fake driver,
# which has no external dependencies.
SUPPORTED_DRIVERS = ['fake']

# NOTE(jroll): resources must be deleted in a specific order, this list
# defines the resource types to clean up, and the correct order.
RESOURCE_TYPES = ['port', 'node', 'chassis']


def creates(resource):
    """Decorator that adds resources to the appropriate cleanup list."""

    def decorator(f):
        @functools.wraps(f)
        def wrapper(cls, *args, **kwargs):
            resp, body = f(cls, *args, **kwargs)

            if 'uuid' in body:
                cls.created_objects[resource].add(body['uuid'])

            return resp, body
        return wrapper
    return decorator


class BaseBaremetalTest(api_version_utils.BaseMicroversionTest,
                        test.BaseTestCase):
    """Base class for Baremetal API tests."""

    credentials = ['admin']

    @classmethod
    def skip_checks(cls):
        super(BaseBaremetalTest, cls).skip_checks()
        if not CONF.service_available.ironic:
            skip_msg = ('%s skipped as Ironic is not available' % cls.__name__)
            raise cls.skipException(skip_msg)

        if CONF.baremetal.driver not in SUPPORTED_DRIVERS:
            skip_msg = ('%s skipped as Ironic driver %s is not supported for '
                        'testing.' %
                        (cls.__name__, CONF.baremetal.driver))
            raise cls.skipException(skip_msg)

        cfg_min_version = CONF.baremetal.min_microversion
        cfg_max_version = CONF.baremetal.max_microversion
        api_version_utils.check_skip_with_microversion(cls.min_microversion,
                                                       cls.max_microversion,
                                                       cfg_min_version,
                                                       cfg_max_version)

    @classmethod
    def get_client_with_isolated_creds(cls,
                                       name=None,
                                       type_of_creds="admin",
                                       api_microversions=None):
        """Creates isolated creds.

        :param name: name, will be used for naming ic and related stuff
        :param type_of_creds: admin, alt or primary
        :param cleanup_in_class: defines place where to delete
        :returns: SharesClient -- shares client with isolated creds.
        :returns: To client added dict attr 'creds' with
        :returns: key elements 'tenant' and 'user'.
        """

        if name is None:
            # Get name of test method
            name = inspect.stack()[1][3]
            if len(name) > 32:
                name = name[0:32]

        # Choose type of isolated creds
        ic = dynamic_creds.DynamicCredentialProvider(
            identity_version=CONF.identity.auth_version,
            name=name,
            admin_role=CONF.identity.admin_role,
            admin_creds=common_creds.get_configured_credentials(
                'identity_admin'))
        if "admin" in type_of_creds:
            creds = ic.get_admin_creds()
        elif "alt" in type_of_creds:
            creds = ic.get_alt_creds()
        else:
            creds = ic.self.get_credentials(type_of_creds)
        ic.type_of_creds = type_of_creds

        # create client with isolated creds
        os = clients.Manager(credentials=creds,
                             api_microversions=api_microversions)
        client = os.baremetal_client

        return client

    @classmethod
    def setup_credentials(cls):
        cls.request_microversion = (
            api_version_utils.select_request_microversion(
                cls.min_microversion,
                CONF.baremetal.min_microversion))
        cls.services_microversion = {
            CONF.baremetal.catalog_type: cls.request_microversion}
        super(BaseBaremetalTest, cls).setup_credentials()

    @classmethod
    def setup_clients(cls):
        super(BaseBaremetalTest, cls).setup_clients()
        cls.client = cls.get_client_with_isolated_creds(
            type_of_creds='admin', api_microversions=cls.services_microversion)

    @classmethod
    def resource_setup(cls):
        super(BaseBaremetalTest, cls).resource_setup()

        cls.driver = CONF.baremetal.driver
        cls.power_timeout = CONF.baremetal.power_timeout
        cls.unprovision_timeout = CONF.baremetal.unprovision_timeout
        cls.created_objects = {}
        for resource in RESOURCE_TYPES:
            cls.created_objects[resource] = set()

    @classmethod
    def resource_cleanup(cls):
        """Ensure that all created objects get destroyed."""

        try:
            for resource in RESOURCE_TYPES:
                uuids = cls.created_objects[resource]
                delete_method = getattr(cls.client, 'delete_%s' % resource)
                for u in uuids:
                    delete_method(u, ignore_errors=lib_exc.NotFound)
        finally:
            super(BaseBaremetalTest, cls).resource_cleanup()

    @classmethod
    @creates('chassis')
    def create_chassis(cls, description=None, expect_errors=False):
        """Wrapper utility for creating test chassis.

        :param description: A description of the chassis. if not supplied,
            a random value will be generated.
        :return: Created chassis.

        """
        description = description or data_utils.rand_name('test-chassis')
        resp, body = cls.client.create_chassis(description=description)
        return resp, body

    @classmethod
    @creates('node')
    def create_node(cls, chassis_id, cpu_arch='x86', cpus=8, local_gb=10,
                    memory_mb=4096):
        """Wrapper utility for creating test baremetal nodes.

        :param cpu_arch: CPU architecture of the node. Default: x86.
        :param cpus: Number of CPUs. Default: 8.
        :param local_gb: Disk size. Default: 10.
        :param memory_mb: Available RAM. Default: 4096.
        :return: Created node.

        """
        resp, body = cls.client.create_node(chassis_id, cpu_arch=cpu_arch,
                                            cpus=cpus, local_gb=local_gb,
                                            memory_mb=memory_mb,
                                            driver=cls.driver)

        return resp, body

    @classmethod
    @creates('port')
    def create_port(cls, node_id, address, extra=None, uuid=None):
        """Wrapper utility for creating test ports.

        :param address: MAC address of the port.
        :param extra: Meta data of the port. If not supplied, an empty
            dictionary will be created.
        :param uuid: UUID of the port.
        :return: Created port.

        """
        extra = extra or {}
        resp, body = cls.client.create_port(address=address, node_id=node_id,
                                            extra=extra, uuid=uuid)

        return resp, body

    @classmethod
    def delete_chassis(cls, chassis_id):
        """Deletes a chassis having the specified UUID.

        :param uuid: The unique identifier of the chassis.
        :return: Server response.

        """

        resp, body = cls.client.delete_chassis(chassis_id)

        if chassis_id in cls.created_objects['chassis']:
            cls.created_objects['chassis'].remove(chassis_id)

        return resp

    @classmethod
    def delete_node(cls, node_id):
        """Deletes a node having the specified UUID.

        :param uuid: The unique identifier of the node.
        :return: Server response.

        """

        resp, body = cls.client.delete_node(node_id)

        if node_id in cls.created_objects['node']:
            cls.created_objects['node'].remove(node_id)

        return resp

    @classmethod
    def delete_port(cls, port_id):
        """Deletes a port having the specified UUID.

        :param uuid: The unique identifier of the port.
        :return: Server response.

        """

        resp, body = cls.client.delete_port(port_id)

        if port_id in cls.created_objects['port']:
            cls.created_objects['port'].remove(port_id)

        return resp

    def validate_self_link(self, resource, uuid, link):
        """Check whether the given self link formatted correctly."""
        expected_link = "{base}/{pref}/{res}/{uuid}".format(
                        base=self.client.base_url,
                        pref=self.client.uri_prefix,
                        res=resource,
                        uuid=uuid)
        self.assertEqual(expected_link, link)
