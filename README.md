docker-registry-driver-alioss
=============================

This is a docker-registry backend driver based on the Open Storage Service from aliyun.com.

Usage
=========

Assuming you have a working docker-registry and oss api setup(you can get it here： http://aliyunecs.oss-cn-hangzhou.aliyuncs.com/OSS_Python_API_20140509.zip).

pip install docker-registry-driver-alioss
or
get source code and run python setup.py install

Edit your configuration so that storage reads ali oss.

Options
=========
You may add any of the following to your main docker-registry configuration to further configure it.


    storage: specify the storage to use, should be alwasy alioss 
    oss_bucket: specify the bucket where you want to store these images for your registry
    oss_accessid: the access id for the oss bucket, which you get from aliyun.com
    oss_accesskey: the access key for the oss bucket, which you get from aliyun.com
    
  example:
  NA
    
License
=========
This is licensed under the Apache license. Most of the code here comes from docker-registry, under an Apache license as well.
