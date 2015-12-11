===================
Ironic and DevStack
===================

This is a guide to configuration parameters that devstack accepts regarding
the Ironic service.

It is not yet a complete list, and only includes sections for Neutron
integration and the use / enrollment of external hardware.
Other sections will be added later.

Build User Image with DIB
=========================

diskimage-builder is a flexible suite of components for building a wide-range
of disk images, filesystem images and ramdisk images for use with OpenStack.
To build user image with DIB use IRONIC_BUILD_USER_IMAGE flag. To pass
additional parameters to diskimage-builder use DIB_VARS, space separated list
of variables. Additional options can be passed with DISK_IMAGE_BUILDER_OPTS,
space separated options list. Image will be uploaded to glance with
ir-user-$IRONIC_DEPLOY_DRIVER name.


::

    IRONIC_BUILD_USER_IMAGE=True

    DISK_IMAGE_BUILDER_OPTS="baremetal ubuntu vm"

    DIB_VARS="DIB_RELEASE=trusty"
