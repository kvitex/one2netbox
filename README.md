


## Configuration

### NetBox Configuration

#### Role creation

You need to define a role under /dcim/device-roles/ that has the 'VM Role' option set.
You need to gather the ID of that role, you'll find that under **/api/**dcim/device-roles/

#### Custom fields creation

* Via the User icon, head to the Admin page http://netbox-url/admin/
* under /admin/extras/customfield/ create the following fields.

In assignment, set 'Objects' to `virtualization -> virtual machine`.


|NAME|MODELS|TYPE|
|----|------|----|
|account|virtual machine|Text|
|created|virtual machine|Date|
|hostname|virtual machine	|Text|
|hypervisor|virtual machine|Text|
|templatename|virtual machine|Text|
|vmid|	virtual machine	|Text|

You can also add validation rules, or a description.



### OpenNebula configuration

You need to have the API accessible (`/etc/one/oned.conf`) as http://one-frontend-url/RPC2/
You need an API user with permissions to read the VM data.


### one2netbox configuration

* copy config.yml.exmp to config.yml
* in config.yml, make adjustments for your credentials and URLs

also adjust your cluster settings:

* cluster name (as seen in NetBox)
* add the cluster's id (as per /api/virtualization/clusters/) 
* add the role id from the "Role creation" step at the start

#### Limitations

There can only be a single OpenNebula cluster configured


### OS configuration

Installing the following dependencies from PyPi should allow the script to run.
```
$ pip3 install pynetbox
$ pip3 install pyone
```


## Usage

run `./DiscoverOneVMs.py`

... one2netbox will connect to OpenNebula and NetBox and then create/update the VM list in NetBox.
(In case of problems, try to work with the json errors returned from NetBox)


A successfully created VM should look something like this in the api under /api/virtualization/virtual-machines/

```
{
            "id": 36,
            "url": "http://netbox-url/api/virtualization/virtual-machines/36/",
            "name": "gamez",
            "status": {
                "value": "offline",
                "label": "Offline"
            },
            "site": {
                "id": 1,
                "url": "http://netbox-url/api/dcim/sites/1/",
                "name": "site-demo",
                "slug": "site-demo"
            },
            "cluster": {
                "id": 1,
                "url": "http://netbox-url/api/virtualization/clusters/1/",
                "name": "demo-place"
            },
            "role": {
                "id": 3,
                "url": "http://netbox-url/api/dcim/device-roles/3/",
                "name": "VM",
                "slug": "vm"
            },
            "tenant": null,
            "platform": null,
            "primary_ip": null,
            "primary_ip4": null,
            "primary_ip6": null,
            "vcpus": 1,
            "memory": 12288,
            "disk": 250,
            "comments": "",
            "local_context_data": null,
            "tags": [],
            "custom_fields": {
                "account": "oneadmin",
                "created": "2020-06-08",
                "hostname": "hypervisor-kvm",
                "hypervisor": "kvm",
                "templatename": "",
                "vmid": "731"
            },
            "config_context": {},
            "created": "2021-02-09",
            "last_updated": "2021-02-09T01:05:52.752243Z"
        },
```
