import os
from datetime import datetime
from math import log

file_type_mapping = {
    "Documents": ["doc", "docx", "pdf", "txt", "xls", "xlsx", "csv", "ppt", "pptx"],
    "Images": ["jpg", "jpeg", "png", "gif", "svg"],
    "Audio": ["mp3", "wav", "aac"],
    "Video": ["mp4", "avi", "mkv"],
    "Archives": ["zip", "rar", "tar", "gz", "tgz"],
    "Code": ["py", "js", "html", "htm", "css", "java", "cpp", "h"],
    "Config": ["json", "yaml", "yml", "xml", "ini"],
    "Executables": ["exe", "sh", "bat"],
    "Misc": ["ttf", "otf"]
}

# Get the full path of the current script
current_script_path = __file__

# Get the file name from the path
current_script_name = os.path.basename(current_script_path)

def get_file_extension(file_name):
    return file_name.lower().split('.')[-1]

def get_file_category(file_name):
    ext = get_file_extension(file_name)
    for category, extensions in file_type_mapping.items():
        if ext in extensions:
            return category
    return "Misc"

def get_files_not_in_folders(directory):
    files_not_in_folders = []
    for item in os.listdir(directory):
        if os.path.isfile(item) and item != current_script_name:
            files_not_in_folders.append(item)
    return files_not_in_folders

def get_formatted_file_size(file_size_in_bytes):
    if file_size_in_bytes == 0:
        return "0 B"
    else: 
        units = ['B', 'KB', 'MB', 'GB']
        exponent = int(log(file_size_in_bytes) / log(1024))
        size = file_size_in_bytes / pow(1024, exponent)
        return f"{size:.2f} {units[exponent]}"

def log_file_details(name):
    # Get file modification timestamp
    mod_ts = os.stat(name).st_mtime
    mod_date_time = datetime.fromtimestamp(mod_ts)

    # Get file size in a formatted way
    file_size = os.stat(name).st_size
    formatted_file_size = get_formatted_file_size(file_size)
    
    # Get file name
    file_name = os.path.basename(name)
    
    # Log the file details
    print(f"File Name: {file_name}")
    print(f"File Size: {formatted_file_size}")
    print(f"Last Modified: {mod_date_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("--------------------------------------------------------------")

os.chdir('/Users/ecaalah/Desktop')
current_directory = os.getcwd()
print("Current Directory = ", current_directory)

files = get_files_not_in_folders(current_directory)
if(len(files) > 0):
    for file in files:
        file_category = get_file_category(file)

        src_file_path = os.path.join(current_directory, file)
        dest_file_path = os.path.join(current_directory, file_category)
        
        """Create new folder if it does not exist"""
        if(not os.path.exists(dest_file_path)):
            os.makedirs(dest_file_path)

        dest_file_path = os.path.join(dest_file_path, file)
        
        log_file_details(file)
        os.rename(src_file_path, dest_file_path)

    print("All files moved successfully!!!")
else:
    print("No files to process!!!")