# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
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

"""Ironic base exception handling.

SHOULD include dedicated exception logging.

"""

from oslo_config import cfg
from oslo_log import log as logging
import six
from six.moves import http_client

from ironic.common.i18n import _
from ironic.common.i18n import _LE
from ironic.common.i18n import _LW


LOG = logging.getLogger(__name__)

exc_log_opts = [
    cfg.BoolOpt('fatal_exception_format_errors',
                default=False,
                help=_('Used if there is a formatting error when generating '
                       'an exception message (a programming error). If True, '
                       'raise an exception; if False, use the unformatted '
                       'message.')),
]

CONF = cfg.CONF
CONF.register_opts(exc_log_opts)


class IronicException(Exception):
    """Base Ironic Exception

    To correctly use this class, inherit from it and define
    a '_msg_fmt' property. That message will get printf'd
    with the keyword arguments provided to the constructor.

    If you need to access the message from an exception you should use
    six.text_type(exc)

    """
    _msg_fmt = _("An unknown exception occurred.")
    code = http_client.INTERNAL_SERVER_ERROR
    headers = {}
    safe = False

    def __init__(self, message=None, **kwargs):
        self.kwargs = kwargs

        if 'code' not in self.kwargs:
            try:
                self.kwargs['code'] = self.code
            except AttributeError:
                pass

        if not message:
            # Check if class is using deprecated 'message' attribute.
            if (hasattr(self, 'message') and self.message):
                LOG.warning(_LW("Exception class: %s Using the 'message' "
                                "attribute in an exception has been "
                                "deprecated. The exception class should be "
                                "modified to use the '_msg_fmt' "
                                "attribute."), self.__class__.__name__)
                self._msg_fmt = self.message

            try:
                message = self._msg_fmt % kwargs

            except Exception as e:
                # kwargs doesn't match a variable in self._msg_fmt
                # log the issue and the kwargs
                LOG.exception(_LE('Exception in string format operation'))
                for name, value in kwargs.items():
                    LOG.error("%s: %s" % (name, value))

                if CONF.fatal_exception_format_errors:
                    raise e
                else:
                    # at least get the core self._msg_fmt out if something
                    # happened
                    message = self._msg_fmt

        super(IronicException, self).__init__(message)

    def __str__(self):
        """Encode to utf-8 then wsme api can consume it as well."""
        if not six.PY3:
            return unicode(self.args[0]).encode('utf-8')

        return self.args[0]

    def __unicode__(self):
        """Return a unicode representation of the exception message."""
        return unicode(self.args[0])


class NotAuthorized(IronicException):
    _msg_fmt = _("Not authorized.")
    code = http_client.FORBIDDEN


class OperationNotPermitted(NotAuthorized):
    _msg_fmt = _("Operation not permitted.")


class Invalid(IronicException):
    _msg_fmt = _("Unacceptable parameters.")
    code = http_client.BAD_REQUEST


class Conflict(IronicException):
    _msg_fmt = _('Conflict.')
    code = http_client.CONFLICT


class TemporaryFailure(IronicException):
    _msg_fmt = _("Resource temporarily unavailable, please retry.")
    code = http_client.SERVICE_UNAVAILABLE


class NotAcceptable(IronicException):
    # TODO(deva): We need to set response headers in the API for this exception
    _msg_fmt = _("Request not acceptable.")
    code = http_client.NOT_ACCEPTABLE


class InvalidState(Conflict):
    _msg_fmt = _("Invalid resource state.")


class NodeAlreadyExists(Conflict):
    _msg_fmt = _("A node with UUID %(uuid)s already exists.")


class MACAlreadyExists(Conflict):
    _msg_fmt = _("A port with MAC address %(mac)s already exists.")


class ChassisAlreadyExists(Conflict):
    _msg_fmt = _("A chassis with UUID %(uuid)s already exists.")


class PortAlreadyExists(Conflict):
    _msg_fmt = _("A port with UUID %(uuid)s already exists.")


class PortgroupAlreadyExists(Conflict):
    _msg_fmt = _("A portgroup with UUID %(uuid)s already exists.")


class PortgroupDuplicateName(Conflict):
    _msg_fmt = _("A portgroup with name %(name)s already exists.")


class PortgroupMACAlreadyExists(Conflict):
    _msg_fmt = _("A portgroup with MAC address %(mac)s already exists.")


class InstanceAssociated(Conflict):
    _msg_fmt = _("Instance %(instance_uuid)s is already associated with a "
                 "node, it cannot be associated with this other node %(node)s")


class DuplicateName(Conflict):
    _msg_fmt = _("A node with name %(name)s already exists.")


class InvalidUUID(Invalid):
    _msg_fmt = _("Expected a uuid but received %(uuid)s.")


class InvalidUuidOrName(Invalid):
    _msg_fmt = _("Expected a logical name or uuid but received %(name)s.")


class InvalidName(Invalid):
    _msg_fmt = _("Expected a logical name but received %(name)s.")


class InvalidIdentity(Invalid):
    _msg_fmt = _("Expected an uuid or int but received %(identity)s.")


class InvalidMAC(Invalid):
    _msg_fmt = _("Expected a MAC address but received %(mac)s.")


class InvalidSwitchID(Invalid):
    _msg_fmt = _("Expected a MAC address or OpenFlow datapath_id but "
                 "received %(switch_id)s.")


class InvalidStateRequested(Invalid):
    _msg_fmt = _('The requested action "%(action)s" can not be performed '
                 'on node "%(node)s" while it is in state "%(state)s".')


class PatchError(Invalid):
    _msg_fmt = _("Couldn't apply patch '%(patch)s'. Reason: %(reason)s")


class InstanceDeployFailure(IronicException):
    _msg_fmt = _("Failed to deploy instance: %(reason)s")


class ImageUnacceptable(IronicException):
    _msg_fmt = _("Image %(image_id)s is unacceptable: %(reason)s")


class ImageConvertFailed(IronicException):
    _msg_fmt = _("Image %(image_id)s is unacceptable: %(reason)s")


# Cannot be templated as the error syntax varies.
# msg needs to be constructed when raised.
class InvalidParameterValue(Invalid):
    _msg_fmt = _("%(err)s")


class MissingParameterValue(InvalidParameterValue):
    _msg_fmt = _("%(err)s")


class Duplicate(IronicException):
    _msg_fmt = _("Resource already exists.")


class NotFound(IronicException):
    _msg_fmt = _("Resource could not be found.")
    code = http_client.NOT_FOUND


class DHCPLoadError(IronicException):
    _msg_fmt = _("Failed to load DHCP provider %(dhcp_provider_name)s, "
                 "reason: %(reason)s")


class DriverNotFound(NotFound):
    _msg_fmt = _("Could not find the following driver(s): %(driver_name)s.")


class ImageNotFound(NotFound):
    _msg_fmt = _("Image %(image_id)s could not be found.")


class NoValidHost(NotFound):
    _msg_fmt = _("No valid host was found. Reason: %(reason)s")


class InstanceNotFound(NotFound):
    _msg_fmt = _("Instance %(instance)s could not be found.")


class NodeNotFound(NotFound):
    _msg_fmt = _("Node %(node)s could not be found.")


class PortgroupNotFound(NotFound):
    _msg_fmt = _("Portgroup %(portgroup)s could not be found.")


class PortgroupNotEmpty(Invalid):
    _msg_fmt = _("Cannot complete the requested action because portgroup "
                 "%(portgroup)s contains ports.")


class NodeAssociated(InvalidState):
    _msg_fmt = _("Node %(node)s is associated with instance %(instance)s.")


class PortNotFound(NotFound):
    _msg_fmt = _("Port %(port)s could not be found.")


class FailedToUpdateDHCPOptOnPort(IronicException):
    _msg_fmt = _("Update DHCP options on port: %(port_id)s failed.")


class FailedToCleanDHCPOpts(IronicException):
    _msg_fmt = _("Clean up DHCP options on node: %(node)s failed.")


class FailedToGetIPAddressOnPort(IronicException):
    _msg_fmt = _("Retrieve IP address on port: %(port_id)s failed.")


class InvalidIPv4Address(IronicException):
    _msg_fmt = _("Invalid IPv4 address %(ip_address)s.")


class FailedToUpdateMacOnPort(IronicException):
    _msg_fmt = _("Update MAC address on port: %(port_id)s failed.")


class ChassisNotFound(NotFound):
    _msg_fmt = _("Chassis %(chassis)s could not be found.")


class NoDriversLoaded(IronicException):
    _msg_fmt = _("Conductor %(conductor)s cannot be started "
                 "because no drivers were loaded.")


class ConductorNotFound(NotFound):
    _msg_fmt = _("Conductor %(conductor)s could not be found.")


class ConductorAlreadyRegistered(IronicException):
    _msg_fmt = _("Conductor %(conductor)s already registered.")


class PowerStateFailure(InvalidState):
    _msg_fmt = _("Failed to set node power state to %(pstate)s.")


class ExclusiveLockRequired(NotAuthorized):
    _msg_fmt = _("An exclusive lock is required, "
                 "but the current context has a shared lock.")


class NodeMaintenanceFailure(Invalid):
    _msg_fmt = _("Failed to toggle maintenance-mode flag "
                 "for node %(node)s: %(reason)s")


class NodeConsoleNotEnabled(Invalid):
    _msg_fmt = _("Console access is not enabled on node %(node)s")


class NodeInMaintenance(Invalid):
    _msg_fmt = _("The %(op)s operation can't be performed on node "
                 "%(node)s because it's in maintenance mode.")


class ChassisNotEmpty(Invalid):
    _msg_fmt = _("Cannot complete the requested action because chassis "
                 "%(chassis)s contains nodes.")


class IPMIFailure(IronicException):
    _msg_fmt = _("IPMI call failed: %(cmd)s.")


class AMTConnectFailure(IronicException):
    _msg_fmt = _("Failed to connect to AMT service. This could be caused "
                 "by the wrong amt_address or bad network environment.")


class AMTFailure(IronicException):
    _msg_fmt = _("AMT call failed: %(cmd)s.")


class MSFTOCSClientApiException(IronicException):
    _msg_fmt = _("MSFT OCS call failed.")


class SSHConnectFailed(IronicException):
    _msg_fmt = _("Failed to establish SSH connection to host %(host)s.")


class SSHCommandFailed(IronicException):
    _msg_fmt = _("Failed to execute command via SSH: %(cmd)s.")


class UnsupportedDriverExtension(Invalid):
    _msg_fmt = _('Driver %(driver)s does not support %(extension)s '
                 '(disabled or not implemented).')


class GlanceConnectionFailed(IronicException):
    _msg_fmt = _("Connection to glance host %(host)s:%(port)s failed: "
                 "%(reason)s")


class ImageNotAuthorized(NotAuthorized):
    _msg_fmt = _("Not authorized for image %(image_id)s.")


class InvalidImageRef(Invalid):
    _msg_fmt = _("Invalid image href %(image_href)s.")


class ImageRefValidationFailed(IronicException):
    _msg_fmt = _("Validation of image href %(image_href)s failed, "
                 "reason: %(reason)s")


class ImageDownloadFailed(IronicException):
    _msg_fmt = _("Failed to download image %(image_href)s, reason: %(reason)s")


class KeystoneUnauthorized(IronicException):
    _msg_fmt = _("Not authorized in Keystone.")


class KeystoneFailure(IronicException):
    pass


class CatalogNotFound(IronicException):
    _msg_fmt = _("Service type %(service_type)s with endpoint type "
                 "%(endpoint_type)s not found in keystone service catalog.")


class ServiceUnavailable(IronicException):
    _msg_fmt = _("Connection failed")


class Forbidden(IronicException):
    _msg_fmt = _("Requested OpenStack Images API is forbidden")


class BadRequest(IronicException):
    pass


class InvalidEndpoint(IronicException):
    _msg_fmt = _("The provided endpoint is invalid")


class CommunicationError(IronicException):
    _msg_fmt = _("Unable to communicate with the server.")


class HTTPForbidden(Forbidden):
    pass


class Unauthorized(IronicException):
    pass


class HTTPNotFound(NotFound):
    pass


class ConfigNotFound(IronicException):
    _msg_fmt = _("Could not find config at %(path)s")


class NodeLocked(Conflict):
    _msg_fmt = _("Node %(node)s is locked by host %(host)s, please retry "
                 "after the current operation is completed.")


class NodeNotLocked(Invalid):
    _msg_fmt = _("Node %(node)s found not to be locked on release")


class NoFreeConductorWorker(TemporaryFailure):
    _msg_fmt = _('Requested action cannot be performed due to lack of free '
                 'conductor workers.')
    code = http_client.SERVICE_UNAVAILABLE


class VendorPassthruException(IronicException):
    pass


class ConfigInvalid(IronicException):
    _msg_fmt = _("Invalid configuration file. %(error_msg)s")


class DriverLoadError(IronicException):
    _msg_fmt = _("Driver %(driver)s could not be loaded. Reason: %(reason)s.")


class ConsoleError(IronicException):
    pass


class NoConsolePid(ConsoleError):
    _msg_fmt = _("Could not find pid in pid file %(pid_path)s")


class ConsoleSubprocessFailed(ConsoleError):
    _msg_fmt = _("Console subprocess failed to start. %(error)s")


class PasswordFileFailedToCreate(IronicException):
    _msg_fmt = _("Failed to create the password file. %(error)s")


class IBootOperationError(IronicException):
    pass


class IloOperationError(IronicException):
    _msg_fmt = _("%(operation)s failed, error: %(error)s")


class IloOperationNotSupported(IronicException):
    _msg_fmt = _("%(operation)s not supported. error: %(error)s")


class DracOperationError(IronicException):
    _msg_fmt = _('DRAC operation failed. Reason: %(error)s')


class DracRequestFailed(IronicException):
    pass


class DracClientError(DracRequestFailed):
    _msg_fmt = _('DRAC client failed. '
                 'Last error (cURL error code): %(last_error)s, '
                 'fault string: "%(fault_string)s" '
                 'response_code: %(response_code)s')


class DracOperationFailed(DracRequestFailed):
    _msg_fmt = _('DRAC operation failed. _msg_fmt: %(_msg_fmt)s')


class DracUnexpectedReturnValue(DracRequestFailed):
    _msg_fmt = _('DRAC operation yielded return value %(actual_return_value)s '
                 'that is neither error nor expected '
                 '%(expected_return_value)s')


class DracPendingConfigJobExists(IronicException):
    _msg_fmt = _('Another job with ID %(job_id)s is already created  '
                 'to configure %(target)s. Wait until existing job '
                 'is completed or is canceled')


class DracInvalidFilterDialect(IronicException):
    _msg_fmt = _('Invalid filter dialect \'%(invalid_filter)s\'. '
                 'Supported options are %(supported)s')


class FailedToGetSensorData(IronicException):
    _msg_fmt = _("Failed to get sensor data for node %(node)s. "
                 "Error: %(error)s")


class FailedToParseSensorData(IronicException):
    _msg_fmt = _("Failed to parse sensor data for node %(node)s. "
                 "Error: %(error)s")


class InsufficientDiskSpace(IronicException):
    _msg_fmt = _("Disk volume where '%(path)s' is located doesn't have "
                 "enough disk space. Required %(required)d MiB, "
                 "only %(actual)d MiB available space present.")


class ImageCreationFailed(IronicException):
    _msg_fmt = _('Creating %(image_type)s image failed: %(error)s')


class SwiftOperationError(IronicException):
    _msg_fmt = _("Swift operation '%(operation)s' failed: %(error)s")


class SwiftObjectNotFoundError(SwiftOperationError):
    _msg_fmt = _("Swift object %(object)s from container %(container)s "
                 "not found. Operation '%(operation)s' failed.")


class SNMPFailure(IronicException):
    _msg_fmt = _("SNMP operation '%(operation)s' failed: %(error)s")


class FileSystemNotSupported(IronicException):
    _msg_fmt = _("Failed to create a file system. "
                 "File system %(fs)s is not supported.")


class IRMCOperationError(IronicException):
    _msg_fmt = _('iRMC %(operation)s failed. Reason: %(error)s')


class IRMCSharedFileSystemNotMounted(IronicException):
    _msg_fmt = _("iRMC shared file system '%(share)s' is not mounted.")


class VirtualBoxOperationFailed(IronicException):
    _msg_fmt = _("VirtualBox operation '%(operation)s' failed. "
                 "Error: %(error)s")


class HardwareInspectionFailure(IronicException):
    _msg_fmt = _("Failed to inspect hardware. Reason: %(error)s")


class NodeCleaningFailure(IronicException):
    _msg_fmt = _("Failed to clean node %(node)s: %(reason)s")


class PathNotFound(IronicException):
    _msg_fmt = _("Path %(dir)s does not exist.")


class DirectoryNotWritable(IronicException):
    _msg_fmt = _("Directory %(dir)s is not writable.")


class UcsOperationError(IronicException):
    _msg_fmt = _("Cisco UCS client: operation %(operation)s failed for node"
                 " %(node)s. Reason: %(error)s")


class UcsConnectionError(IronicException):
    _msg_fmt = _("Cisco UCS client: connection failed for node "
                 "%(node)s. Reason: %(error)s")


class WolOperationError(IronicException):
    pass


class ImageUploadFailed(IronicException):
    _msg_fmt = _("Failed to upload %(image_name)s image to web server "
                 "%(web_server)s, reason: %(reason)s")


class CIMCException(IronicException):
    _msg_fmt = _("Cisco IMC exception occurred for node %(node)s: %(error)s")


class OneViewError(IronicException):
    _msg_fmt = _("OneView exception occurred. Error: %(error)s")
