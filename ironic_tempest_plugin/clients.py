# Copyright 2012 OpenStack Foundation
# All Rights Reserved.
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

from tempest import clients
from tempest import config

from ironic_tempest_plugin.services.baremetal.v1.json import baremetal_client

CONF = config.CONF


class Manager(clients.Manager):
    def __init__(self, credentials, service=None, api_microversions=None):
        """Initialization of Manager class.

        Setup all services clients and make them available for tests cases.
        :param credentials: type Credentials or TestResources
        :param service: Service name
        :param api_microversions: This is dict of services catalog type
               and their microversion which will be set on respective
               services clients.
               {<service catalog type>: request_microversion}
               Example :
                {'compute': request_microversion}
                    - request_microversion will be set on all compute
                      service clients.
                OR
                {'compute': request_microversion,
                 'volume': request_microversion}
                    - request_microversion of compute will be set on all
                      compute service clients.
                    - request_microversion of volume will be set on all
                      volume service clients.
        """
        super(Manager, self).__init__(credentials, service, api_microversions)
        self.baremetal_client = baremetal_client.BaremetalClient(
            self.auth_provider,
            CONF.baremetal.catalog_type,
            CONF.identity.region,
            endpoint_type=CONF.baremetal.endpoint_type,
            **self.default_params_with_timeout_values)
        self._set_api_microversions()
