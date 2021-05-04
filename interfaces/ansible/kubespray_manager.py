import os
import re
import yaml
import shutil
import logging
import dpath.util
import ansible_runner

from exceptions.exceptions import ConfigurationException
from fs import file_utils
from models.models import ServerNodeModel

logger = logging.getLogger(__name__)


class KubesprayPatcher:

    def __init__(self, kubespray_dir, patches):
        self.patch_state = {}
        self.patches = patches
        self.target_dir = os.path.join(kubespray_dir, 'inventory/group_vars')
        self.dpath_regex = re.compile(r'^[a-zA-Z0-9_-][a-zA-Z0-9_\-[\]\/]*$')

    def validate_patches(self):
        for patch in self.patches:
            patch_path = patch.get('path', None)
            file, path = self.__get_patch_tuple(patch_path)
            if os.path.isabs(path) or file.startswith('/') or ':' in file or '\\' in file:
                raise ConfigurationException(f'Patch {patch_path} start seems to be invalid')
            if os.path.exists(os.path.join(self.target_dir, patch_path)):
                raise ConfigurationException(f'Patch {patch_path} points to a non existing file')
            if not path or not self.dpath_regex.match(path):
                raise ConfigurationException(f'Patch {patch_path} dpath {path} is invalid')
            if 'value' not in patch:
                raise ConfigurationException(f'Patch {patch_path} has no patching value')

    @staticmethod
    def __get_patch_tuple(patch_path):
        if not patch_path:
            raise ConfigurationException('A patch without path is present')
        split_path = patch_path.strip().split('|')
        if not split_path or len(split_path) != 2:
            raise ConfigurationException(f'{patch_path} is not a valid patch path')
        return split_path[0], split_path[1]

    def patch(self):
        for patch in self.patches:
            file_rel_path, path = self.__get_patch_tuple(patch.get('path', None))
            if file_rel_path not in self.patch_state:
                with open(os.path.join(self.target_dir, file_rel_path), 'r') as file:
                    self.patch_state[file_rel_path] = yaml.full_load(file)
            dpath.util.new(self.patch_state.get(file_rel_path), path, patch.get('value'))

        for file_path, patch_state in self.patch_state.items():
            with open(os.path.join(self.target_dir, file_path), 'w') as target_file:
                yaml.dump(patch_state, target_file, width=float("inf"))


class KubesprayManager:

    def __init__(self, context, resources):
        if not context:
            raise TypeError('context cannot be null')

        if resources is None:
            raise TypeError('resources cannot be null')

        self.resources = resources
        self.context = context
        self.current_inventory = None
        self.content_folder = None

    @staticmethod
    def __build_inventory(resources):
        if resources is None:
            raise TypeError('resources cannot be null')

        #TODO Be aware of naming changes in kubespray
        inventory = {'all': {'hosts': {}, 'children': {}}}
        inventory['all']['children']['kube-master'] = {'hosts': {}}
        inventory['all']['children']['kube-node'] = {'hosts': {}}
        inventory['all']['children']['calico-rr'] = {'hosts': {}}
        inventory['all']['children']['etcd'] = {'hosts': {}}
        inventory['all']['children']['k8s-cluster'] = {'children': {
            'kube-master': {},
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

            if server_node.roles and 'kube-master' in server_node.roles:
                inventory['all']['children']['kube-master']['hosts'][server_node.name] = {}

            if server_node.roles and 'kube-node' in server_node.roles:
                inventory['all']['children']['kube-node']['hosts'][server_node.name] = {}

            inventory['all']['hosts'][server_node.name] = host_node

        return inventory

    def initialize(self):

        self.current_inventory = self.__build_inventory(self.resources)
        self.content_folder = self.context.kubespray_config.package_manager.get_content()

        # Copy sample inventory
        dest = shutil.copytree(os.path.join(self.content_folder, 'inventory/sample/group_vars'),
                               os.path.join(self.content_folder, 'inventory/group_vars'))

        # Delete sample inventory.ini (usually not present)
        file_utils.safe_file_delete(os.path.join(dest, 'inventory.ini'))

        # Prepare ssh pk. Write to env/ssh_key or at least load it to provide it to ansible as a param

        # Apply config patches
        KubesprayPatcher(self.content_folder, self.context.kubespray_config.patches).patch()

    def create_cluster(self):
        # Initialize if not already done
        if not self.content_folder:
            self.initialize()

        ##################### FILES TO PREPARE #######################
        # !! Clone kubespray. It's root directory will be known as 'proyect_base'
        # proyect_base/env/ssh_key => SSH PK to access remote servers
        # proyect_base/inventory/hosts => Ansible inventory file as usual
        # proyect_base/inventory/group_vars => All the files inside the original kubespray vars examples. Edit as needed.

        # TODO Temporal until SSH key management is implemented
        os.makedirs(os.path.join(self.content_folder, 'inventory/env'))
        shutil.copyfile(os.path.join(os.path.expanduser('~'), '.ssh/id_rsa'),
                        os.path.join(self.content_folder, 'inventory/env/shh_key'))

        #TODO Temporal
        r = ansible_runner.run(
            private_data_dir=self.content_folder,
            playbook='cluster.yml',
            project_dir=self.content_folder,
            cmdline='-u root -b',
            inventory=self.current_inventory
        )

        logger.info(f'Kubespray run finished. Result: {r}')
