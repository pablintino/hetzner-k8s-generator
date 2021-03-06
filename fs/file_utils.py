import os
import shutil
import pathlib


def move_content_to_parent(directory_path, delete_directory=True):
    path = pathlib.Path(directory_path)
    if path == path.parent and delete_directory:
        raise ValueError('cannot move and delete directory cause if fs root')
    for filename in os.listdir(directory_path):
        shutil.move(os.path.join(directory_path, filename), os.path.join(path.parent, filename))

    if delete_directory:
        os.rmdir(directory_path)


def get_file_as_text(path):
    try:
        with open(path, 'r') as file:
            return file.read()
    except OSError:
        return None


def get_create_dir_if_not_exists(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    return dir_path


def safe_file_delete(path):
    if path:
        try:
            os.remove(path)
        except OSError:
            pass
