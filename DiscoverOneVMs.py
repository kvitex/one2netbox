#!/usr/bin/env python3
import pynetbox
import yaml
import datetime
import ipaddress
import pyone
import collections


def ctime():
    return str(datetime.datetime.now())


def one2netbox_vm_status(one_state):
    status_dict = {3: 1}
    return status_dict.get(one_state, 0)


def netbox_update_vm(one_vm, nb_update_vm):
    nb_update_vm.name = one_vm['name']
    nb_update_vm.memory = int(one_vm['memory'])
    nb_update_vm.vcpus = int(one_vm['vcpus'])
    nb_update_vm.disk = int(one_vm['disk'])
    nb_update_vm.status = one_vm['status']
    nb_update_vm.custom_fields = one_vm['custom_fields']
    update_result = None
    try:
        update_result = nb_update_vm.save()
    except pynetbox.RequestError as Error:
        update_result = None
    return update_result


def one_vm_diskspace(one_vm):
    vm_template = one_vm.TEMPLATE.get('DISK')
    if type(vm_template) == list:
        diskspace = sum(list(map(lambda ds: int(ds['SIZE']), vm_template)))
    elif isinstance(vm_template, collections.OrderedDict):
        diskspace = int(vm_template['SIZE'])
    else:
        diskspace = 0
    return diskspace

def one_vm_nics(one_vm):
    nics = one_vm.TEMPLATE.get('NIC')
    if type(nics) == list:
        return list(map(lambda nic: {'name': 'eth{}'.format(nic['NIC_ID']),
                                     'ip': nic.get('IP'),
                                     'mask': '24',
                                     'mac': nic['MAC']
                                     }, nics))
    elif isinstance(nics, collections.OrderedDict):
        return [{'name': 'eth{}'.format(nics['NIC_ID']),
                'ip': nics.get('IP'),
                'mask': '24',
                'mac' : nics['MAC']
                 },]
    return None

if __name__ == "__main__":
    config_file_name = 'config.yml'
    try:
        with open(config_file_name) as config_file:
            cfg = yaml.load(config_file.read())
    except FileNotFoundError or FileExistsError as Error:
        print('Can not open configuration file {}'.format(config_file_name))
        print(Error)
        exit(-1)
    except yaml.scanner.ScannerError as Error:
        print('Error while parsing configuration file {}'.format(config_file_name))
        print(Error)
        exit(-1)
    except Exception as Error:
        print(Error)
        exit(-1)
    try:
        nb = pynetbox.api(**cfg['netbox'])
    except KeyError as Error:
        print('Netbox configuration not found.')
        exit(-1)
    except Exception as Error:
        print('PyNetbox: ', Error)
        exit(-1)
    try:
        one = pyone.OneServer(cfg['one']['endpoint'], session=cfg['one']['credentials'])
        one_vms = one.vmpool.info(-2, -1, -1, -1).VM
        one_tmp_pool = one.templatepool.info(-2,-1,-1).VMTEMPLATE
        template_dict = dict(tuple(map(lambda tmp: (tmp.ID, tmp.NAME), one_tmp_pool)))
        cluster_name = cfg['cluster_name']
        cluster_id = cfg['cluster_id']
        vm_role_id = cfg['vm_role_id']
    except KeyError as Error:
        print('OpenNebula configuration not found.')
        exit(-1)
    except Exception as Error:
        print('OpenNebula: ', Error)
        exit(-1)
    netbox_vms = nb.virtualization.virtual_machines.filter(cluster_id=cluster_id)
# Getting platforms from netbox and making dictionary with slugs as a key
    platforms_dict = dict(map(lambda nb_pl: (nb_pl.slug, nb_pl.id), nb.dcim.platforms.all()))
# Serialize OpenNebula VM data
    s_vms = []
    for one_vm in one_vms:
        # print(one_vm.NAME, '\t', one_vm.TEMPLATE['TEMPLATE_ID'])
        s_vms.append({'name': one_vm.NAME,
                      'role': vm_role_id,
                      'cluster': cluster_id,
                      'vcpus': one_vm.TEMPLATE['VCPU'],
                      'memory': one_vm.TEMPLATE['MEMORY'],
                      'disk': one_vm_diskspace(one_vm) // 1024,
                      'status': one2netbox_vm_status(one_vm.STATE),
                      'custom_fields': {'vmid': str(one_vm.ID),
                                        'account': one_vm.UNAME,
                                        'hostname': one_vm.HISTORY_RECORDS.HISTORY[0].HOSTNAME,
                                        'templatename': template_dict[int(one_vm.TEMPLATE['TEMPLATE_ID'])],
                                        'hypervisor': one_vm.HISTORY_RECORDS.HISTORY[0].VM_MAD,
                                        'created': str(datetime.datetime.fromtimestamp(one_vms[3].STIME).date())}
                       ,'one_nics': one_vm_nics(one_vm)
                      })
# Checking if VM in Netbox is exist in CloudStack. If not, then deleting VM in Netbox
    netbox_vm_deleted = False
    for netbox_vm in netbox_vms:
        netbox_vm_exist = False
        for one_vm in s_vms:
            if netbox_vm.custom_fields['vmid'] == one_vm['custom_fields']['vmid']:
                netbox_vm_exist = True
                break
        if not netbox_vm_exist:
            print('{} Virtual machine name={} id={} not found in {}. Deleting from netbox'.
                  format(ctime(), netbox_vm.name, netbox_vm.custom_fields['vmid'], cluster_name))
            if not netbox_vm.delete():
                print('{} Can not delete from netbox virtual machine name={} id={}'.
                      format(ctime(), netbox_vm.name, netbox_vm.custom_fields['vmid']))
            else:
                netbox_vm_deleted = True
    if netbox_vm_deleted:
        netbox_vms = nb.virtualization.virtual_machines.filter(cluster_id=cluster_id)
# Creating a set of netbox VM IDs for further check if VM from OpenNebula already exists in netbox
    netbox_vmid_dict = dict(tuple(map(lambda netbox_vm: (netbox_vm.custom_fields['vmid'], netbox_vm.id), netbox_vms)))
    vms_added = 0
    for one_vm in s_vms:
        vmid = one_vm['custom_fields']['vmid']
        # print(one_vm)
        if vmid in netbox_vmid_dict.keys():
            try:
                nb_update_vm = nb.virtualization.virtual_machines.get(netbox_vmid_dict[vmid])
            except:
                print('{} Netbox error while getting VM netbox id={}'.format(ctime(), vmid))
            finally:
                vm_update_result = netbox_update_vm(one_vm, nb_update_vm)
                if vm_update_result == True:
                    print('{} Updated VM name={} id={}'.format(ctime(), one_vm['name'], vmid))
                elif vm_update_result == False:
                    print('{} Nothing to update VM name={} id={}'.format(ctime(), one_vm['name'], vmid))
                else:
                    print('{} Netbox error while updating name={} id={}'.format(ctime(), one_vm['name'], vmid))
        else:
            print('{} Creating in netbox virtual machine name={} id={}'.
                  format(ctime(), one_vm['name'], vmid))
            nb_vm_args = one_vm
            nb_new_vm = None
            try:
                nb_new_vm = nb.virtualization.virtual_machines.create(**nb_vm_args)
                if not nb_new_vm:
                    print('{} Error while Creating in netbox virtual machine name={} id={} nb_vm_args={}'.
                          format(ctime(), one_vm['name'], one_vm['id'], nb_vm_args))
            except pynetbox.RequestError as Error:
                print('{} Exception "{}" while Creating in netbox virtual machine name={} id={} nb_vm_args={}'.
                      format(ctime(), Error,one_vm['name'], one_vm['id'], nb_vm_args))
            # print(nb_new_vm)
            if nb_new_vm:
                no_primary_ip = True
                for i in range(len(one_vm['one_nics'])):
                    this_nic = one_vm['one_nics'][i]
                    nb_int_args = {'virtual_machine': nb_new_vm.id,
                                   'name': 'eth{}'.format(i),
                                   'mac_address': this_nic['mac'],
                                   'form_factor': 0
                                   }
                    # print(nb_int_args)

                    nb_new_int = None
                    try:
                        nb_new_int = nb.virtualization.interfaces.create(**nb_int_args)
                        # print(nb_new_int)
                        if nb_new_int:
                            nb_ip_args = {'status': 1,
                                          'address': '{}/{}'.format(this_nic['ip'], this_nic['mask'])
                                          }
                            #print(nb_ip_args)
                            nb_new_ip = None
                            if this_nic['ip']:
                                nb_new_ip = nb.ipam.ip_addresses.create(**nb_ip_args)
                            if nb_new_ip:
                                # nb_update_interface = nb.virtualization.interfaces.get(nb_new_int['id'])
                                # print(nb_new_ip)
                                nb_update_ip = nb.ipam.ip_addresses.get(nb_new_ip.id)
                                nb_update_ip.interface = nb_new_int.id
                                if nb_update_ip.save() and no_primary_ip:
                                    nb_update_vm = nb.virtualization.virtual_machines.get(nb_new_vm.id)
                                    nb_update_vm.primary_ip4 = nb_update_ip
                                    nb_update_vm.primary_ip = nb_update_ip
                                    nb_update_vm.save()
                                    no_primary_ip = False
                    except pynetbox.RequestError as Error:
                        print('{} Exception "{}" while Creating  netbox VM interface  name={} nic={}'.
                              format(ctime(), Error, one_vm['name'], this_nic))
            vms_added += 1
            #exit(0)
    print('{} All {} VMs added successfully'.format(ctime(), vms_added))
