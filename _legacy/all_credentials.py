# This program file is only to fetch credentials which will be used to log into host devices and not the jump host.
import json

# We fetch the data from .JSON everytime because we get to see the latest value while the code is running live.
# The below is the structure of the credentials being saved.
structure = {
    'client_name':
        {
            'username': '',
            'password': ''
        },
}


# To add and save a new credentials to a save file.
# Can add only one credential at a time.
def credential_save(payload: dict):  # The payload should be in the defined dictionary structure.
    # Ensure that payload['client_name'] is always set as .lower()
    try:
        all_data = json.load(open('client_credentials.json'))  # Storing all .JSON file in a variable.
        # Below for loop is experimental. It is used to compare the values of 2 different dicts.
        for values in all_data.values():  # Obtaining data from each client
            for new_value in payload.values():  # Obtaining value/credential content from payload
                if new_value == values:
                    # This indicates that the new entry is duplicate.
                    return 1062  # Common Error code indicating duplicate entry
                else:
                    with open('client_credentials.json', 'w') as writing_mode:
                        json.dump(all_data.update(payload.values()), writing_mode,
                                  indent=6)  # Appending values directly to the existing client details
                        writing_mode.close()
                    return True
    except FileNotFoundError:
        # If file is non-existent. The below block will create and append the values automatically. This is usually done once.
        with open('client_credentials.json', 'a+') as file_open:
            json.dump(payload, file_open, indent=6)
            file_open.close()
        return True
    except Exception as e:
        return e


# To delete data from the existing .json file.
def delete_credentials(payload: dict):
    try:
        all_data = json.load(open('client_credentials.json'))
        writing_mode = open('client_credentials.json', 'w')
        if payload['client_name'] in all_data.keys():
            if payload['delete_type'] == 1:  # This only deletes one credential for a client
                all_data.pop(payload['client_name'][payload['client_credentials']].values())
                json.dump(all_data, writing_mode, indent=6)
                writing_mode.close()
                return True
            elif payload['delete_type'] == 2:  # Erase all the save of the client
                all_data.pop(payload['client_name'])
                json.dump(all_data, writing_mode, indent=6)
                writing_mode.close()
                return True
            elif payload['delete_type'] == 3:  # Clear complete .JSON [All save for all client will be erased]
                all_data.clear()
                json.dump(all_data, writing_mode, indent=6)
                writing_mode.close()
                return True
            else:
                return False
        else:
            writing_mode.close()
            return 14  # If the client details is not available on the .JSON
    except FileNotFoundError:
        return 404
    except Exception as e:
        return e


# I need to write a function to edit/update the existing credentials
# Need to check once
def edit_creds(client_name, credentials: dict):
    try:
        all_data = json.load(open('client_credentials.json'))
        writing_mode = open('client_credentials.json', 'w')
        json.dump(all_data[client_name].update(credentials), writing_mode, indent=6)
        writing_mode.close()
        return
    except FileNotFoundError:
        return 404


# To gather all the available clients
def fetch_clients():
    try:
        return json.load(open('client_credentials.json')).keys()
    except FileNotFoundError:
        return 404


# To fetch the data related to client from the list of save file.
def client_credential_fetch(client_name):
    try:
        all_data = json.load(open('client_credentials.json'))
        if client_name in all_data.keys():
            return all_data[client_name]
        else:
            return False
    except FileNotFoundError:
        return 404
