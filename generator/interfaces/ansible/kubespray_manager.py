import glob
import os
import ansible_runner
import logging

import yaml

from generator.models.models import ServerNodeModel

logger = logging.getLogger(__name__)


def build_inventory(resources):
    if resources is None:
        raise TypeError('resources cannot be null')

    inventory = {'all': {'hosts': {}, 'children': {}}}
    inventory['all']['children']['kube_control_plane'] = {'hosts': {}}
    inventory['all']['children']['kube-node'] = {'hosts': {}}
    inventory['all']['children']['calico-rr'] = {'hosts': {}}
    inventory['all']['children']['etcd'] = {'hosts': {}}
    inventory['all']['children']['k8s-cluster'] = {'children': {
        'kube_control_plane': {},
        'kube-node': {},
        'calico-rr': {},
    }}

    for server_node in [inst for inst in resources if isinstance(inst, ServerNodeModel)]:

        internal_ip = server_node.network_interfaces[0].ip if server_node.network_interfaces else None
        host_node = {'ansible_host': server_node.public_ip}

        if internal_ip:
            host_node['ip'] = internal_ip

        if server_node.roles and 'etcd' in server_node.roles:
            host_node['etcd_member_name'] = 'etcd-' + server_node.name
            inventory['all']['children']['etcd']['hosts'][server_node.name] = {}

        if server_node.roles and 'kube_control_plane' in server_node.roles:
            inventory['all']['children']['kube_control_plane']['hosts'][server_node.name] = {}

        if server_node.roles and 'kube-node' in server_node.roles:
            inventory['all']['children']['kube-node']['hosts'][server_node.name] = {}

        inventory['all']['hosts'][server_node.name] = host_node

    return inventory


def update_config_files(kubespray_inventory_dir, patches_directory):
    for yml_path in glob.glob(patches_directory + '/**/*.yml', recursive=True):

        # TODO Remove this hardcoded value
        rel_patch = os.path.relpath(yml_path, '/home/pablintino/Sources/k8s/config/kubespray-config')

        with open(yml_path, 'r') as patch:
            patch_values = yaml.full_load(patch)

        target_path = os.path.join(kubespray_inventory_dir, rel_patch)
        with open(target_path, 'r') as target:
            old_values = yaml.full_load(target)
            for patch_key, patch_value in patch_values.items():
                old_values[patch_key] = patch_value

        with open(target_path, 'w') as target_file:
            yaml.dump(old_values, target_file, width=float("inf"))


def create_cluster(resource_list):
    if resource_list is None:
        raise TypeError('resource_list cannot be null')

    inventory = build_inventory(resource_list)

    ansible_settings = {'become': 'true', 'become_user': 'root'}
    # TODO Remove hardcoded var
    kubespray_dir = '/home/pablintino/Desktop/kubespray'

    ##################### FILES TO PREPARE #######################
    # !! Clone kubespray. It's root directory will be known as 'proyect_base'
    # proyect_base/env/ssh_key => SSH PK to access remote servers
    # proyect_base/inventory/hosts => Ansible inventory file as usual
    # proyect_base/inventory/group_vars => All the files inside the original kubespray vars examples. Edit as needed.

    r = ansible_runner.run(
        private_data_dir=kubespray_dir,
        playbook='cluster.yml',
        project_dir=kubespray_dir,
        settings=ansible_settings,
        inventory=inventory
    )

    logger.info(f'Kubespray run finished. Result: {r}')