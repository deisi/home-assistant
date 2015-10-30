"""
homeassistant.components.device_tracker.fritz
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unfortunately, you have to execute the following command by hand:
sudo apt-get install libxslt-dev libxml2-dev

Device tracker platform that supports scanning a FitzBox router for device
presence.

Configuration:

To use the fritz tracker you have to adapt your configuration.yaml by
using the following template:

device_tracker:
  platform: fritz
  host: YOUR_ROUTER_IP
  username: YOUR_ADMIN_USERNAME
  password: YOUR_ADMIN_PASSWORD

host
*Optional
The IP address of your router, e.g. 192.168.0.1.
It is optional since every fritzbox is also reachable by using the 169.254.1.1 IP.

username
*Optional
The username of an user with administrative privileges, usually 'admin'.
However, it seems that it is not necessary to use it in current generation fritzbox routers
because the necessary data can be retrieved anonymously.

password
*Optional
The password for your given admin account.
However, it seems that it is not necessary to use it in current generation fritzbox routers
because the necessary data can be retrieved anonymously.
"""
import logging
from datetime import timedelta

from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import validate_config
from homeassistant.util import Throttle
from homeassistant.components.device_tracker import DOMAIN

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['fritzconnection==0.4.6']


def get_scanner(hass, config):
    """ Validates config and returns FritzBoxScanner"""
    if not validate_config(config,
                           {DOMAIN: []},
                           _LOGGER):
        return None
    scanner = FritzBoxScanner(config[DOMAIN])
    return scanner if scanner.success_init else None


# pylint: disable=too-many-instance-attributes
class FritzBoxScanner(object):
    """ This class queries a FritzBox router. It is using the
    fritzconnection library for communication with the router.

    The API description can be found under:
    https://pypi.python.org/pypi/fritzconnection/0.4.6

    This scanner retrieves the list of known hosts and checks
    their corresponding states (on, or off).

    Due to a bug of the fritzbox api (router side) it is not possible
    to track more than 16 hosts."""
    def __init__(self, config):
        self.last_results = []

        try:
            # noinspection PyPackageRequirements,PyUnresolvedReferences
            import fritzconnection as fc
        except ImportError:
            _LOGGER.exception("""Failed to import Python library fritzconnection.
                              Please run <home-assistant>/scripts/setup to install it.""")
            self.success_init = False
            return

        host = '169.254.1.1'  # this is valid for all fritzboxes
        if CONF_HOST in config.keys():
            host = config[CONF_HOST]
        password = ''
        if CONF_PASSWORD in config.keys():
            password = config[CONF_PASSWORD]
        self._fritz_box = fc.FritzHosts(address=host, password=password)
        # I have not found a way to validate login, at least for
        # my fritzbox, i can get the list of known hosts even without
        # password
        self.success_init = True

        if self.success_init:
            self._update_info()
        else:
            _LOGGER.error("Failed to login into FritzBox")

    def scan_devices(self):
        """ Scans for new devices and return a
            list containing found device ids. """
        self._update_info()
        active_hosts = []
        for known_host in self.last_results:
            if known_host["status"] == "1":
                active_hosts.append(known_host["mac"])
        return active_hosts

    def get_device_name(self, mac):
        """ Returns the name of the given device or None if not known. """

        ret = self._fritz_box.get_specific_host_entry(mac)["NewHostName"]
        if ret == {}:
            return None
        return ret

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """ Retrieves latest information from the FritzBox.
            Returns boolean if scanning successful. """
        if not self.success_init:
            return

        _LOGGER.info("Scanning")
        self.last_results = self._fritz_box.get_hosts_info()
