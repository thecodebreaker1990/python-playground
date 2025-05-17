import os
from datetime import datetime

def get_file_extension(file_name):
    file_parts = file_name.split('.')
    extension = file_parts.pop().strip()
    return extension

def log_file_folder_details(name, i):
    mod_ts = os.stat(name).st_mtime
    mod_date_time = datetime.fromtimestamp(mod_ts)
    if(os.path.isdir(name)):
        print('No. {0}. {1} is a folder'.format(i+1, name))
    else:
        print('No. {0}. {1}, extension = {2}'.format(i+1, name, get_file_extension(name)))

current_directory = os.getcwd()
print('Current directory = {0}'.format(current_directory))

for dirpath, dirnames, filenames in os.walk(current_directory):
    print('Current Path:', dirpath)
    print('Directories:', dirnames)
    print('Files:', filenames)

"""Get User's Home directory by querying the environment variables"""
home_dir = os.environ.get('HOME')
file_path = os.path.join(home_dir, 'test.txt')
print(file_path)

file_name = os.path.basename(file_path)
print(file_name)

"""Check if a path exists or not"""
is_valid_path = os.path.exists(file_path);
print(is_valid_path)

"""Create a new directory"""
# new_directory = 'advanced-python'
# os.mkdir(new_directory)

"""Rename a file"""
# os.rename('sample3.txt', 'test.txt')

"""Iterate over files and folders in a directory"""
# list_of_files_folders = os.listdir()
# for i, name in enumerate(list_of_files_folders):
#     log_file_folder_details(name, i)

"""Change directory"""
# os.chdir('/Users/ecaalah/Desktop')
# updated_directory = os.getcwd()
# print('Updated directory = {0}'.format(updated_directory))