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

import testtools

from tempest.api.compute.floating_ips import base
from tempest.common import utils
from tempest import config
from tempest.lib.common.utils import test_utils
from tempest.lib import decorators
from tempest.lib import exceptions as lib_exc

CONF = config.CONF


class FloatingIPsTestJSON(base.BaseFloatingIPsTest):

    @classmethod
    def skip_checks(cls):
        super(FloatingIPsTestJSON, cls).skip_checks()
        if not utils.get_service_list()['network']:
            raise cls.skipException("network service not enabled.")
        if not CONF.network_feature_enabled.floating_ips:
            raise cls.skipException("Floating ips are not available")

    @classmethod
    def setup_clients(cls):
        super(FloatingIPsTestJSON, cls).setup_clients()
        cls.client = cls.floating_ips_client

    @classmethod
    def resource_setup(cls):
        super(FloatingIPsTestJSON, cls).resource_setup()

        # Server creation
        server = cls.create_test_server(wait_until='ACTIVE')
        cls.server_id = server['id']
        # Floating IP creation
        body = cls.client.create_floating_ip(
            pool=CONF.network.floating_network_name)['floating_ip']
        cls.addClassResourceCleanup(cls.client.delete_floating_ip, body['id'])
        cls.floating_ip_id = body['id']
        cls.floating_ip = body['ip']

    @decorators.idempotent_id('f7bfb946-297e-41b8-9e8c-aba8e9bb5194')
    def test_allocate_floating_ip(self):
        # Positive test:Allocation of a new floating IP to a project
        # should be successful
        body = self.client.create_floating_ip(
            pool=CONF.network.floating_network_name)['floating_ip']
        floating_ip_id_allocated = body['id']
        self.addCleanup(self.client.delete_floating_ip,
                        floating_ip_id_allocated)
        floating_ip_details = self.client.show_floating_ip(
            floating_ip_id_allocated)['floating_ip']
        # Checking if the details of allocated IP is in list of floating IP
        body = self.client.list_floating_ips()['floating_ips']
        self.assertIn(floating_ip_details, body)

    @decorators.idempotent_id('de45e989-b5ca-4a9b-916b-04a52e7bbb8b')
    def test_delete_floating_ip(self):
        # Positive test:Deletion of valid floating IP from project
        # should be successful
        # Creating the floating IP that is to be deleted in this method
        floating_ip_body = self.client.create_floating_ip(
            pool=CONF.network.floating_network_name)['floating_ip']
        self.addCleanup(test_utils.call_and_ignore_notfound_exc,
                        self.client.delete_floating_ip, floating_ip_body['id'])
        # Deleting the floating IP from the project
        self.client.delete_floating_ip(floating_ip_body['id'])
        # Check it was really deleted.
        self.client.wait_for_resource_deletion(floating_ip_body['id'])

    @decorators.idempotent_id('307efa27-dc6f-48a0-8cd2-162ce3ef0b52')
    @testtools.skipUnless(CONF.network.public_network_id,
                          'The public_network_id option must be specified.')
    def test_associate_disassociate_floating_ip(self):
        # Positive test:Associate and disassociate the provided floating IP
        # to a specific server should be successful

        # Association of floating IP to fixed IP address
        self.client.associate_floating_ip_to_server(
            self.floating_ip,
            self.server_id)

        # Check instance_id in the floating_ip body
        body = (self.client.show_floating_ip(self.floating_ip_id)
                ['floating_ip'])
        self.assertEqual(self.server_id, body['instance_id'])

        # Disassociation of floating IP that was associated in this method
        self.client.disassociate_floating_ip_from_server(
            self.floating_ip,
            self.server_id)

    @decorators.idempotent_id('6edef4b2-aaf1-4abc-bbe3-993e2561e0fe')
    @testtools.skipUnless(CONF.network.public_network_id,
                          'The public_network_id option must be specified.')
    def test_associate_already_associated_floating_ip(self):
        # positive test:Association of an already associated floating IP
        # to specific server should change the association of the Floating IP
        # Create server so as to use for Multiple association
        body = self.create_test_server(wait_until='ACTIVE')
        self.new_server_id = body['id']
        self.addCleanup(self.servers_client.delete_server, self.new_server_id)

        # Associating floating IP for the first time
        self.client.associate_floating_ip_to_server(
            self.floating_ip,
            self.server_id)
        # Associating floating IP for the second time
        self.client.associate_floating_ip_to_server(
            self.floating_ip,
            self.new_server_id)

        self.addCleanup(self.client.disassociate_floating_ip_from_server,
                        self.floating_ip,
                        self.new_server_id)

        # Make sure no longer associated with old server
        self.assertRaises((lib_exc.NotFound,
                           lib_exc.UnprocessableEntity,
                           lib_exc.Conflict),
                          self.client.disassociate_floating_ip_from_server,
                          self.floating_ip, self.server_id)
