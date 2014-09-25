# -*- coding: utf-8 -*-
"""
docker_registry.drivers.alioss
~~~~~~~~~~~~~~~~~~~~~~~~~~

oss is Open Storage Service provided by aliyun.com
See http://www.aliyun.com

"""

import os
import logging

import oss.oss_api as oss

from docker_registry.core import driver
from docker_registry.core import exceptions
from docker_registry.core import lru

logger = logging.getLogger(__name__)



DEFAUL_OSS_HOST = 'oss.aliyuncs.com'
DEFAULT_OSS_ACCESSID = '<your access id>'
DEFAULT_OSS_ACCESSKEY = '<your access secret>'
DEFAULT_OSS_BUCKET = '<your oss bucket>'
DEFAULT_TIME_OUT = 60

class OssCfg(object):
    def __init__(self):
        self.host = None
        self.accessid = None
        self.accesskey = None
        self.bucket = None

class Storage(driver.Base):

    def __init__(self, path=None, config=None):
        # Turn on streaming support
        self.supports_bytes_range = True
        # Increase buffer size up to 640 Kb
        self.buffer_size = 128 * 1024
        #another stupid bug, oss api wont write an absolute path('/a/b/c'), neither throws any exception
        self._rootpath = path if path[0] != '/' else path[1:]

        self.osscfg = OssCfg()
        self.osscfg.host = (config.oss_host or DEFAUL_OSS_HOST)
        self.osscfg.accessid = (config.oss_accessid or DEFAULT_OSS_ACCESSID)
        self.osscfg.accesskey = (config.oss_accesskey or DEFAULT_OSS_ACCESSKEY)
        self.osscfg.bucket = (config.oss_bucket or DEFAULT_OSS_BUCKET)
        self._oss = oss.OssAPI(self.osscfg.host, self.osscfg.accessid, self.osscfg.accesskey)

    def getfullpath(self, path):
        res = self._rootpath
        if not path:
            res = self._rootpath
        else:
            if path.startswith(self._rootpath):
                res = path
            else:
                res = os.path.join(self._rootpath, path)
        return res

    @lru.get
    def get_content(self, path):
        path = self.getfullpath(path)
        try:
            res = self._oss.get_object(self.osscfg.bucket, path)
            if res.status == 200:
                return res.read()
            else:
                raise IOError('read %s failed, status: %s' % (path, res.status))
        except Exception:
            raise exceptions.FileNotFoundError("File not found %s" % path)

    @lru.set
    def put_content(self, path, content):
        tmppath = path
        path = self.getfullpath(path)
        logger.debug("put_content %s %d", path, len(content))
        self._oss.put_object_with_data(self.osscfg.bucket, path, content)
        return tmppath

    def stream_write(self, path, fp):
        path = self.getfullpath(path)
        try:
            #it is stupid that oss_api uses  fp.seek(os.SEEK_SET, os.SEEK_END)
            #here, write the content to a local file to workaround
            import tempfile
            temp = tempfile.NamedTemporaryFile()
            l = fp.read(self.buffer_size)
            logger.debug('stream_write, begin to write the content to tmpfile')
            while len(l) > 0:
                temp.write(l)
                l = fp.read(self.buffer_size)
            logger.debug('stream_write, wrote the content to tmpfile done')
            temp.seek(0)
            self._oss.put_object_from_fp(self.osscfg.bucket, path, temp)
            temp.close()
        except IOError as err:
            logger.error("unable to read from a given socket %s", err)

    def stream_read(self, path):
        path = self.getfullpath(path)
        logger.debug("read from %s", path)
        if not self.exists(path):
            raise exceptions.FileNotFoundError(
                'No such directory: \'{0}\''.format(path))

        res = self._oss.get_object(self.osscfg.bucket, path)
        if res.status == 200:
            block = res.read(self.buffer_size)
            yield block
        else:
            raise IOError('read %s failed, status: %s' % (path, res.status))

    def list_directory(self, path=None):
        path = self.getfullpath(path)
        objectList = self._oss.list_objects(self.osscfg.bucket, path)
        for item in objectList:
            yield item

    def exists(self, path):
        path = self.getfullpath(path)
        logger.debug("Check existance of %s", path)
        try:
            # read is used instead of lookup
            # just for future quorum reading check
            self.get_size(path)
        except exceptions.FileNotFoundError:
            logger.debug("%s doesn't exist", path)
            return False
        else:
            logger.debug("%s exists", path)
            return True

    @lru.remove
    def remove(self, path):
        path = self.getfullpath(path)
        try:
            for subdir in self.list_directory(path):
                self._oss.delete_object(self.osscfg.bucket, subdir)
        except exceptions.FileNotFoundError as err:
            logger.warning(err)
        self._oss.delete_object(self.osscfg.bucket, path)

    def get_size(self, path):
        path = self.getfullpath(path)
        logger.debug("get_size of %s", path)
        headers = {}
        r = self._oss.head_object(self.osscfg.bucket, path, headers)
        if (r.status/100) != 2:
            raise exceptions.FileNotFoundError(
                "Unable to get size of %s" % path)

        header_map = convert_header2map(r.getheaders())
        size = safe_get_element("content_length", header_map)
        logger.debug("size of %s = %d", path, size)
        return size


def safe_get_element(name, container):
    for k, v in container.items():
        if k.strip().lower() == name.strip().lower():
            return v
    return ""

def convert_header2map(header_list):
    header_map = {}
    for (a, b) in header_list:
        header_map[a] = b
    return header_map
