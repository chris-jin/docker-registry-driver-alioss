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
from oss.oss_xml_handler import GetInitUploadIdXml
from oss.oss_util import get_part_xml, convert_header2map, safe_get_element

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
        self.buffer_size = 2 * 1024 * 1024
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
            logger.debug('init_multi_upload ing...')
            upload_id = ""
            res = self._oss.init_multi_upload(self.osscfg.bucket, path, None)
            if res.status != 200:
                logger.debug('init_multi_upload failed')
                raise IOError("Can not initialize uploading to oss")

            logger.debug('init_multi_upload suceeded')
            body = res.read()
            h = GetInitUploadIdXml(body)
            upload_id = h.upload_id

            part_number = 1
            l = fp.read(self.buffer_size)
            logger.debug('stream_write, begin to write the content to oss')
            while len(l) > 0:
                res = self._oss.upload_part_from_string(self.osscfg.bucket, path, l, upload_id, '%s' % part_number)
                if (res.status / 100) == 2:
                    logger.info('write part %s to %s on oss succeeded' % (part_number, path))
                else:
                    msg = 'write part %s to %s on oss failed' % (part_number, path)
                    logger.error(msg)
                    raise IOError(msg)
                part_number += 1
                l = fp.read(self.buffer_size)
            #complete the upload
            part_msg_xml = get_part_xml(self._oss, self.osscfg.bucket, path, upload_id)
            res = self._oss.complete_upload(self.osscfg.bucket, path, upload_id, part_msg_xml)
            if (res.status / 100) == 2:
                logger.info('stream write to %s finished' % path)
            else:
                msg = 'write to %s on oss failed' % path
                logger.error(msg)
                raise IOError(msg)
        except IOError as err:
            logger.error("unable to read from a given socket %s", err)

    def stream_read(self, path, bytes_range=None):
        path = self.getfullpath(path)
        logger.debug("read from %s", path)
        if not self.exists(path):
            raise exceptions.FileNotFoundError(
                'No such directory: \'{0}\''.format(path))

        res = self._oss.get_object(self.osscfg.bucket, path)
        if res.status == 200:
            block = res.read(self.buffer_size)
            while len(block) > 0:
                yield block
                block = res.read(self.buffer_size)
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
        size = safe_get_element("content-length", header_map)
        logger.debug("size of %s = %d", path, size)
        return size

