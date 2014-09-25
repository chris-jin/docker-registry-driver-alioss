docker-registry-driver-alioss
=============================

This is a docker-registry backend driver based on the Open Storage Service from aliyun.com.

Usage
=========

Assuming you have a working docker-registry and oss api setup(you can get it here： http://aliyunecs.oss-cn-hangzhou.aliyuncs.com/OSS_Python_API_20140509.zip).

    get source code and run:
    python setup.py install

Edit your configuration so that storage reads ali oss.

Config
=========
You should add all the following configurations to your main docker-registry configuration to further configure it, which by default is  config/config.yml.
    
    alioss configrations:
        * storage: specify the storage to use, should be alwasy alioss 
        * storage_path: specify the path prefix in the oss bucket
        * oss_bucket: specify the bucket where you want to store these images for your registry
        * oss_accessid: the access id for the oss bucket, which you get from aliyun.com
        * oss_accesskey: the access key for the oss bucket, which you get from aliyun.com

    example <you can copy this example into your config.yml, and modify it accordingly>:
    
    oss: &oss
        <<: *common
        storage: alioss
        storage_path: _env:STORAGE_PATH:/devregistry/
        oss_bucket: _env:OSS_BUCKET[:default_value]
        oss_accessid: _env:OSS_KEY[:your_access_id]
        oss_accesskey: _env:OSS_SECRET[:your_access_key]

Options
=========
When you run docker-registry, you can use the following two methods to configure the storage:

    * if you run docker-registry on your local host, export these configurations if you want to modify the default value in the configured in the config.yml:
        export SETTINGS_FLAVOR=oss
        export STORAGE_PATH=<the prefix of the storage path>
        export OSS_BUCKET=<your oss bucket>
        export OSS_KEY=<your access id>
        export OSS_SECRET=<your access key>
    
    * if you run docker-registry on your docker container, remmeber to specify these settings as cmd args:
        docker run \
         -e SETTINGS_FLAVOR=oss \
         -e STORAGE_PATH=/dockerregistry/ \
         -e OSS_BUCKET=docker-registry \
         -e OSS_KEY=<your access id> \
         -e OSS_SECRET=<your access key> \
         -e SEARCH_BACKEND=sqlalchemy \
         -p 5000:5000 \
         registry
    
License
=========
This is licensed under the Apache license. Most of the code here comes from docker-registry, under an Apache license as well.
