===============================================
Tempest Integration of Ironic
===============================================

This directory contains Tempest tests to cover the Ironic project.

To list all Congress tempest cases, go to tempest directory, then run::

    $ testr list-tests ironic

To run only these tests in tempest, go to tempest directory, then run::

    $ ./run_tempest.sh -N -- ironic

To run a single test case, go to tempest directory, then run with test case name, e.g.::

    $ ./run_tempest.sh -N -- ironic_tempest_plugin.tests.scenario.test_baremetal_basic_ops.BaremetalBasicOps.test_baremetal_server_ops

Alternatively, to run congress tempest plugin tests using tox, go to tempest directory, then run::

    $ tox -eall-plugin ironic

And, to run a specific test::

    $ tox -eall-plugin ironic_tempest_plugin.tests.scenario.test_baremetal_basic_ops.BaremetalBasicOps.test_baremetal_server_ops
