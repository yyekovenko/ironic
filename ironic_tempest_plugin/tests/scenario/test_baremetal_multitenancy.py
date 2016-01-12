#
# Copyright (c) 2015 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslo_log import log as logging

from tempest import config
from tempest import test
from tempest.common.utils import data_utils
from tempest.scenario import manager
from tempest.services.network import resources as net_resources

CONF = config.CONF

LOG = logging.getLogger(__name__)


class BaremetalMultitenancy(manager.BaremetalScenarioTest,
                            manager.NetworkScenarioTest):
    """Check L2 isolation of baremetal instances in different tenants:

    * Create a keypair, network, subnet and router for the primary tenant
    * Boot two instances in the tenant's network using the keypair
    * Associate floating ips to both instance
    * Verify L2 connectivity exists between instances of the same tenant
    * Delete one of the instances
    * Create a keypair, network, subnet and router for the alt tenant
    * Boot an instance in the alt tenant's network
    * Associate floating ip to the instance
    * Verify there is no L2 connectivity between instances of different tenants
    * Delete both instances
    """

    credentials = ['primary', 'alt', 'admin']

    def create_tenant_network(self, clients, tenant_cidr):
        network = self._create_network(
            client=clients.network_client,
            networks_client=clients.networks_client,
            tenant_id=clients.credentials.tenant_id)
        router = self._get_router(
            client=clients.network_client,
            tenant_id=clients.credentials.tenant_id)

        result = clients.subnets_client.create_subnet(
            name=data_utils.rand_name('subnet'),
            network_id=network['id'],
            tenant_id=clients.credentials.tenant_id,
            ip_version=4,
            cidr=tenant_cidr)
        subnet = net_resources.DeletableSubnet(
            network_client=clients.network_client,
            subnets_client=clients.subnets_client,
            **result['subnet'])
        self.addCleanup(self.delete_wrapper, subnet.delete)
        subnet.add_to_router(router.id)

        return network, subnet, router

    def verify_l2_connectivity(self, source_ip, private_key,
                               destination_ip, conn_expected=True):
        remote = self.get_remote_client(source_ip, private_key=private_key)

        cmd = 'case $(sudo arping -c 4 {}) in ' \
              '*"0 reply"*) echo -ne "ISOLATED" ;; ' \
              '*"4 reply"*) echo -ne "CONNECTED" ;; ' \
              'esac'.format(destination_ip)

        output = remote.exec_command(cmd)
        if conn_expected:
            self.assertEqual("CONNECTED", output)
        else:
            self.assertEqual("ISOLATED", output)

    @test.idempotent_id('26e2f145-2a8e-4dc7-8457-7f2eb2c6749d')
    @test.services('baremetal', 'compute', 'image', 'network')
    def test_baremetal_multitenancy(self):

        tenant_cidr = '10.0.100.0/24'
        fixed_ip1 = '10.0.100.3'
        fixed_ip2 = '10.0.100.5'
        fixed_ip3 = '10.0.100.7'

        keypair = self.create_keypair()
        network, subnet, router = self.create_tenant_network(
            self.manager, tenant_cidr)

        # Boot 2 instances in the primary tenant network
        # and check L2 connectivity between them
        instance1, node1 = self.boot_instance(
            clients=self.manager,
            keypair=keypair,
            net_id=network['id'],
            fixed_ip=fixed_ip1
        )
        floating_ip1 = self.create_floating_ip(
            instance1,
            client=self.floating_ips_client
        )['floating_ip_address']
        self.check_vm_connectivity(ip_address=floating_ip1,
                                   private_key=keypair['private_key'])

        instance2, node2 = self.boot_instance(
            clients=self.manager,
            keypair=keypair,
            net_id=network['id'],
            fixed_ip=fixed_ip2
        )
        floating_ip2 = self.create_floating_ip(
            instance2,
            client=self.floating_ips_client
        )['floating_ip_address']

        self.check_vm_connectivity(ip_address=floating_ip2,
                                   private_key=keypair['private_key'])
        self.verify_l2_connectivity(
            floating_ip1,
            keypair['private_key'],
            fixed_ip2
        )
        self.verify_l2_connectivity(
            floating_ip2,
            keypair['private_key'],
            fixed_ip1
        )

        self.terminate_instance(instance2, node2)

        # Boot instance in the alt tenant network and ensure there is no
        # L2 connectivity between instances of the different tenants
        alt_keypair = self.create_keypair(self.alt_manager.keypairs_client)
        alt_network, alt_subnet, alt_router = self.create_tenant_network(
            self.alt_manager, tenant_cidr)

        alt_instance, alt_node = self.boot_instance(
            keypair=alt_keypair,
            clients=self.alt_manager,
            net_id=alt_network['id'],
            fixed_ip=fixed_ip3
        )
        alt_floating_ip = self.create_floating_ip(
            alt_instance,
            client=self.alt_manager.floating_ips_client
        )['floating_ip_address']
        self.check_vm_connectivity(ip_address=alt_floating_ip,
                                   private_key=alt_keypair['private_key'])

        self.verify_l2_connectivity(
            alt_floating_ip,
            alt_keypair['private_key'],
            fixed_ip1,
            conn_expected=False
        )

        self.verify_l2_connectivity(
            floating_ip1,
            keypair['private_key'],
            fixed_ip3,
            conn_expected=False
        )

        self.terminate_instance(
            alt_instance, alt_node,
            servers_client=self.alt_manager.servers_client
        )
        self.terminate_instance(instance1, node1)
