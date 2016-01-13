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

"""Add network_provider as an attribute to node

Revision ID: abedf32345d
Revises: 5ea1b0d310e
Create Date: 2015-01-28 14:28:22.212790

"""

# revision identifiers, used by Alembic.
revision = 'abedf32345d'
down_revision = '5ea1b0d310e'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('nodes', sa.Column('network_provider',
                                     sa.String(length=255),
                                     nullable=True))


def downgrade():
    op.drop_column('nodes', 'network_provider')
