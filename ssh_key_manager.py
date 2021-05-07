import os

from exceptions.exceptions import ConfigurationException, SSHKeysException

from Crypto.PublicKey import RSA


class SshRsaKeyManager:
    def __init__(self, options):
        self.ssh_dir = os.path.join(os.path.expanduser('~'), '.ssh')
        # TODO Make this work with relative paths
        default_pk_path = os.path.join(self.ssh_dir, 'id_rsa')
        default_pub_path = os.path.join(self.ssh_dir, 'id_rsa.pub')
        self.pk_path = options.pk_rsa_key if hasattr(options, 'pk_rsa_key') and options.pk_rsa_key else default_pk_path
        self.pub_path = options.pub_rsa_key if hasattr(options,
                                                       'pub_rsa_key') and options.pub_rsa_key else default_pub_path
        self.pk_data = None
        self.pub_data = None
        self.pk_passphrase = options.pk_passphrase if hasattr(options,
                                                              'pk_passphrase') and options.pk_passphrase else None

    @staticmethod
    def __load_key_from_file(key_path, passphrase=None):
        with open(key_path, "rb") as pk_file:
            try:
                key = RSA.import_key(pk_file.read(), passphrase=passphrase)
            except ValueError:
                raise SSHKeysException('Cannot load private SSH Key. Incorrect passphrase')
            return key.exportKey().decode("utf-8")

    def load(self):
        self.pk_data = self.__load_key_from_file(self.pk_path, self.pk_passphrase)
        if not self.pk_data:
            raise ConfigurationException('Cannot read the selected SSH private key')

        self.pub_data = self.__load_key_from_file(self.pub_path)
        if not self.pub_data:
            raise ConfigurationException('Cannot read the selected SSH public key')