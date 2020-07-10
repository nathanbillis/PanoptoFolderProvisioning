#!python3
import sys
import argparse
import requests
import urllib3
import csv

from panopto_folders import PanoptoFolders

from os.path import dirname, join, abspath
sys.path.insert(0, abspath(join(dirname(__file__), '..', 'common')))
from panopto_oauth2 import PanoptoOAuth2

# Top level folder is represented by zero GUID.
# However, it is not the real folder and some API beahves differently than actual folder.
GUID_TOPLEVEL = '00000000-0000-0000-0000-000000000000'

# Define File Locations
csvLocation = "folders.csv"
resultsCsv = "results.csv"

# Enables double checking if the move is correct, shows things down by adding more user checks.
doubleVerify = False

def parse_argument():
    parser = argparse.ArgumentParser(description='Sample of Folders API')
    parser.add_argument('--server', dest='server', required=True, help='Server name as FQDN')
    parser.add_argument('--client-id', dest='client_id', required=True, help='Client ID of OAuth2 client')
    parser.add_argument('--client-secret', dest='client_secret', required=True, help='Client Secret of OAuth2 client')
    parser.add_argument('--skip-verify', dest='skip_verify', action='store_true', required=False, help='Skip SSL certificate verification. (Never apply to the production code)')
    return parser.parse_args()

def main():
    args = parse_argument()
    panoptoSiteLocation = "https://" + args.server

    if args.skip_verify:
        # This line is needed to suppress annoying warning message.
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Use requests module's Session object in this example.
    # ref. https://2.python-requests.org/en/master/user/advanced/#session-objects
    requests_session = requests.Session()
    requests_session.verify = not args.skip_verify
    
    # Load OAuth2 logic
    oauth2 = PanoptoOAuth2(args.server, args.client_id, args.client_secret, not args.skip_verify)

    # Load Folders API logic
    folders = PanoptoFolders(args.server, not args.skip_verify, oauth2)
    
    current_folder_id = GUID_TOPLEVEL
    print("\n-------------")

    print("\nWelcome to the Panopto Folder Renaming/Moving Tool folders to be processed should be in " + csvLocation +
          " and the results will be stored in " + resultsCsv)
    print("You are logged into " + panoptoSiteLocation)

    print("\n-------------")
    print("What Subject is being processed? (eg. Biology)")
    newSubjectFolder = search_folder(folders)
    subjectFolder = newSubjectFolder[0]
    print("-------------")

    # Display and select Subfolders
    subFolder = get_and_select_sub_folders(folders, subjectFolder)
    print("-------------")

    # Check if selected folder is correct
    print("Once confirmed the script will start iterating through the " + csvLocation
          + " file and rename/move the folders")
    print("\nYou have selected the subject: " + newSubjectFolder[1] +
          "\nYou have selected the subfolder: " + subFolder[1])
    print("\n-------------")
    doubleCheck = input("Please confirm if the above settings are correct: (y) ")
    if doubleCheck.lower() != 'y':
        exit()

    # Select correct folder
    # subFolder = find_year_folder(folders,subjectFolder,folderYear)
    print("---------")

    with open(resultsCsv, mode='w') as resultsCsvfile:
        fieldnames = ['oldName', 'newName', 'success','urlLink']
        csv_writer = csv.DictWriter(resultsCsvfile, fieldnames=fieldnames)
        csv_writer.writeheader()

        with open(csvLocation, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Find and Move Folder
                newFolderName = row['newName']

                print("Module Code: " + newFolderName)
                print("Searching for: " + row['oldName'])
                oldFolderName = search_folder_with_query(folders, row['oldName'])

                success = "N"
                urlLink = 'Folder Not Found'

                if(row['oldName'] == "null-shared"):
                    urlLink = 'TO CHECK - SHARED'


                if(str(oldFolderName) != "None"):
                    if(doubleVerify == True):
                        verify = input ("Are you sure? (enter 'y' to continue or 'n' to abort)")
                    else:
                        verify = 'y'

                    if(verify.lower() == 'y'):
                        moveSuccess = False
                        nameSuccess = folders.update_folder_name(oldFolderName,newFolderName)

                        if nameSuccess:
                            moveSuccess = folders.update_folder_parent(oldFolderName,subFolder[0], subFolder[1])

                        if nameSuccess and moveSuccess == False:
                            print("Could not move due to conflict however renamed sucessfully!")
                            success = "Renamed but did not Move due to conflict"
                            renameSuccess = rename_and_move(folders, oldFolderName, newFolderName, subFolder)
                            if renameSuccess:
                                print("Renamed and Moved Sucessfully!")
                                success = "Y - modified name"

                        if nameSuccess == False and moveSuccess == False:
                            print("Could not rename or move! - This is due to the folder name already being "
                                  "present in the parent directory")
                            success = "N - Failed please try manually"

                        if nameSuccess and moveSuccess:
                            success = "Y"
                        urlLink = panoptoSiteLocation + "/Panopto/Pages/Sessions/List.aspx#folderID=" + oldFolderName

                csv_writer.writerow({'oldName':str(row['oldName']), 'newName':str(row['newName']), 'success':success, 'urlLink':urlLink })
                print("---------")



    
def get_and_display_folder(folders, folder_id):
    '''
    Returning folder object that is returned by API.
    None if it is top level folder.
    '''
    print()
    print('Folder:')
    if folder_id == GUID_TOPLEVEL:
        print('  Top level folder (no detail informaiton is available)')
        return None

    folder = folders.get_folder(folder_id)
    print('  Name: {0}'. format(folder['Name']))
    print('  Id: {0}'. format(folder['Id']))
    if folder['ParentFolder'] is None:
        print('  Parent Folder: Top level folder')
    else:
        print('  Parent Folder: {0}'. format(folder['ParentFolder']['Name']))
    print('  Folder URL: {0}'. format(folder['Urls']['FolderUrl']))
    print('  Embed URL: {0}'. format(folder['Urls']['EmbedUrl']))
    print('  Share settings URL: {0}'. format(folder['Urls']['ShareSettingsUrl']))
    return folder

def get_and_display_sub_folders(folders, current_folder_id):
    print()
    print('Sub Folders:')
    children = folders.get_children(current_folder_id)

    # returning object is the dictionary, key (integer) and folder's ID (UUID)
    result = {}
    key = 0
    for entry in children:
        result[key] = entry['Id']
        print('  [{0}]: {1}'.format(key, entry['Name']))
        key += 1
    
    return result

def get_and_select_sub_folders(folders, current_folder_id):
    print('Sub Folders:')
    children = folders.get_children(current_folder_id)

    # returning object is the dictionary, key (integer) and folder's ID (UUID)
    result = {}
    name = {}
    key = 0
    for entry in children:
        result[key] = entry['Id']
        name[key] = entry['Name']
        print('  [{0}]: {1}'.format(key, entry['Name']))
        key += 1

    selection = input('Enter the folder number: ')

    try:
        key = int(selection)
        if result[key]:
            return result[key], name[key]
    except:
        pass  # selection is not a number, fall through


def process_selection(folders, current_folder, sub_folders):
    if current_folder is None:
        new_folder_id = GUID_TOPLEVEL
        parent_folder_id = GUID_TOPLEVEL
    else:
        new_folder_id = current_folder['Id']
        if current_folder['ParentFolder'] is None:
            parent_folder_id = GUID_TOPLEVEL
        else:
            parent_folder_id = current_folder['ParentFolder']['Id']

    print()
    print('[P] Go to parent')
    print('[R] Rename this folder')
    print('[D] Delete this folder')
    print('[S] Search folders')
    print('[L] List sessions in the folder')
    print()
    selection = input('Enter the command (select number to move folder): ')

    try:
        key = int(selection)
        if sub_folders[key]:
            return sub_folders[key]
    except:
        pass # selection is not a number, fall through

    if selection.lower() == 'p':
        new_folder_id = parent_folder_id
    elif selection.lower() == 'r' and current_folder is not None:
        rename_folder(folders, current_folder)
    elif selection.lower() == 'd' and current_folder is not None:
        if delete_folder(folders, current_folder):
            new_folder_id = parent_folder_id
    elif selection.lower() == 's':
        result = search_folder(folders)
        if result is not None:
            new_folder_id = result
    elif selection.lower() == 'l' and current_folder is not None:
        list_sessions(folders, current_folder)
    else:
        print('Invalid command.')
    
    return new_folder_id

def rename_folder(folders, folder):
    new_name = input('Enter new name: ')
    return folders.update_folder_name(folder['Id'], new_name)
    
def delete_folder(folders, folder):
    return folders.delete_folder(folder['Id'])

def search_folder(folders):
    query = input('Enter search keyword: ')
    entries = folders.search_folders(query)

    if len(entries) == 0:
        print('  No hit.')
        return None

    for index in range(len(entries)):
        print('  [{0}]: {1}'.format(index, entries[index]['Name']))
    selection = input('Enter the number: ')
    
    new_folder_id = None
    try:
        index = int(selection)
        if 0 <= index < len(entries):
            new_folder_id = entries[index]['Id']
            new_folder_name = entries[index]['Name']
    except:
        pass

    return new_folder_id, new_folder_name


def search_folder_with_query(folders, query):
    entries = folders.search_folders(query)

    if len(entries) == 0:
        print('  No hit.')
        return None

    for index in range(len(entries)):
        print('  [{0}]: {1}'.format(index, entries[index]['Name']))
    selection = input('Enter the number: ')

    new_folder_id = None
    try:
        index = int(selection)
        if 0 <= index < len(entries):
            new_folder_id = entries[index]['Id']
    except:
        pass

    return new_folder_id


def list_sessions(folders, folder):
    print('Sessions in the folder:')
    for entry in folders.get_sessions(folder['Id']):
        print('  {0}: {1}'.format(entry['Id'], entry['Name']))

def find_year_folder(folders, current_folder_id, query):
    print()
    print('Sub Folders:')
    children = folders.get_children(current_folder_id)

    # returning object is the dictionary, key (integer) and folder's ID (UUID)
    result = {}
    for entry in children:
        if entry['Name'] == query:
            result = entry['Id']
            print(entry["Name"])

    return result


def get_old_folder(folders):
    query = input('Enter search keyword: ')
    entries = folders.search_folders(query)

    if len(entries) == 0:
        print('  No hit.')
        return None

    for index in range(len(entries)):
        print('  [{0}]: {1}'.format(index, entries[index]['Name']))
    selection = input('Enter the number: ')

    new_folder_id = None
    try:
        index = int(selection)
        if 0 <= index < len(entries):
            new_folder_id = entries[index]
    except:
        pass

    return new_folder_id

def rename_and_move(folders, oldFolderName, newFolderName, subFolder):
    rename = input("Would you like to rename and try again? (y) ")
    if rename.lower() == 'y':
        print("The conflicting name is: " + newFolderName)
        updatedFolderName = input("Please enter new name EXACTLY as you want to call the folder: ")
        nameSuccess = folders.update_folder_name(oldFolderName, updatedFolderName)
        moveSuccess = folders.update_folder_parent(oldFolderName, subFolder[0], subFolder[1])

        if moveSuccess == False or nameSuccess == False:
            print("Error conflicting name: " + updatedFolderName)
            updatedFolderName = input("Please enter new name EXACTLY as you want to call the folder: ")
            nameSuccess = folders.update_folder_name(oldFolderName, updatedFolderName)
            moveSuccess = folders.update_folder_parent(oldFolderName, subFolder[0], subFolder[1])

        if nameSuccess and moveSuccess:
            return True
        else:
            return False


if __name__ == '__main__':
    main()
