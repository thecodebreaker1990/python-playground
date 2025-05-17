def encrypt(text, shift):
    encrypted_text = ""
    for char in text:
        # Shift each character by 'shift' positions
        new_char = chr((ord(char) + shift) % 256)
        encrypted_text += new_char
    return encrypted_text


def decrypt(encrypted_text, shift):
    decrypted_text = ""
    for char in encrypted_text:
        # Shift each character back by 'shift' positions
        new_char = chr((ord(char) - shift) % 256)
        decrypted_text += new_char
    return decrypted_text


def show_welcome_message():
    welcome_message = """
  Welcome to Credential Manager
  ----------------------------
  Select one of the below options to proceed -
  1. Add New Credential.
  2. Get Credential.
  3. Update Credential.
  4. Delete Credential.
  """
    print(welcome_message)


def get_user_input(query):
    user_input = input(query)
    return user_input


def validate_user_input(input):
    try:
        input_number = int(input)
        return input_number >= 1 and input_number <= 4
    except:
        return input.lower() == "exit"


def get_credential_string_template(credential):
    return """##start_{account}##
user_id:{user_id}
password:{password}
##end_{account}##""".format(**credential)


def get_formatted_credential(user_id, password):
    return """
User ID: {0}
Password: {1}
""".format(user_id, password)


def remove_newline_from_string_end(str):
    last_char = str[-1]
    if last_char == "\n":
        return str[:-1]
    else:
        return str


def encrypt_and_write(text, shift):
    """Composed function to encrypt text and write it to a file."""
    encrypted_text = encrypt(text, shift)
    return store_credential_in_file(encrypted_text)


def store_credential_in_file(credential_str):
    f = open("acc-pwd.txt", "a")
    f.write(credential_str)
    f.write("\n")
    f.close()
    return True


def decrypt_and_read(shift):
    """Composed function to read from a file and decrypt it"""
    text = read_credential_from_file()
    decrypted_text = decrypt(text, shift)
    return decrypted_text


def read_credential_from_file():
    try:
        f = open("acc-pwd.txt", "r")
        content = f.read()
        f.close()
        return content
    except:
        return ""


def encrypt_and_update(text, shift):
    """Composed function to encrypt text and write it to a file."""
    encrypted_text = encrypt(text, shift)
    return update_credential_in_file(encrypted_text)


def update_credential_in_file(credential_str):
    f = open("acc-pwd.txt", "w")
    f.write(credential_str)
    f.close()
    return True


def initiate_add_new_credential(account):
    user_id = get_user_input("Enter User ID: ")
    password = get_user_input("Enter Password: ")

    credential_info = {
        'account': account.lower(),
        'user_id': user_id,
        'password': password
    }
    credential_template = get_credential_string_template(credential_info)
    return credential_template


def get_specific_credential(cred_str, cred_type):
    formatted_cred_type = "{0}:".format(cred_type)
    draft_segments = cred_str.split(formatted_cred_type, 1)
    final_segments = draft_segments[1].split("\n", 1)
    return final_segments[0]


def get_raw_credential_for_account(account):
    cred_info_list = []
    account = account.lower()

    all_credentials = decrypt_and_read(4)
    credential_start_statement = "##start_{0}##".format(account)

    credential_start_idx = all_credentials.find(credential_start_statement)

    if credential_start_idx > -1:
        cred_info_list.append(credential_start_idx)
        credential_end_statement = "##end_{0}##".format(account)

        credential_end_idx = all_credentials.find(credential_end_statement)
        cred_info_list.append(credential_end_idx +
                              len(credential_end_statement))

        credential_start_idx = credential_start_idx + len(
            credential_start_statement)

        raw_data = all_credentials[credential_start_idx:credential_end_idx]
        cred_info_list.append(raw_data)
    else:
        cred_info_list = [-1, -1, None]

    return cred_info_list


def get_credential_for_account(account):
    credential_list = get_raw_credential_for_account(account)
    raw_credential = credential_list[-1]
    if (raw_credential is None):
        return None

    user_id = get_specific_credential(raw_credential, "user_id")
    password = get_specific_credential(raw_credential, "password")

    return get_formatted_credential(user_id, password)


def update_credential_for_account(account, start_idx, end_idx):
    user_id = get_user_input("Enter User ID: ")
    password = get_user_input("Enter Password: ")

    credential_info = {
        'account': account.lower(),
        'user_id': user_id,
        'password': password
    }
    credential_template = get_credential_string_template(credential_info)

    all_credentials = decrypt_and_read(4)
    
    print(start_idx, end_idx)

    # all_credential_first_segment = remove_newline_from_string_end(
    #     all_credentials[0:start_idx])
    # all_credentials_final_segment = all_credentials[end_idx]

    # updated_credential = "\n".join([
    #     all_credential_first_segment, credential_template,
    #     all_credentials_final_segment
    # ])

    # return encrypt_and_update(updated_credential, 4)
    return True


def delete_credential_for_account(start_idx, end_idx):
    all_credentials = decrypt_and_read(4)

    all_credential_first_segment = remove_newline_from_string_end(
        all_credentials[0:start_idx])
    all_credentials_final_segment = all_credentials[end_idx:]

    updated_credential = "\n".join(
        [all_credential_first_segment, all_credentials_final_segment])

    return encrypt_and_update(updated_credential, 4)


def main():
    show_welcome_message()
    while (True):
        user_input = get_user_input(
            "Type a number between 1 - 4, or type exit to close the application: "
        )
        if validate_user_input(user_input):
            if (user_input == "exit"):
                print("Exiting Password Manager...")
                break
            else:
                user_input = int(user_input)
                if user_input == 1:
                    ### Start Add new Credential ###
                    account = get_user_input("Enter Account Name: ")
                    credential_list = get_raw_credential_for_account(account)
                    if credential_list[-1] is None:
                        new_cred_template = initiate_add_new_credential(
                            account)
                        encrypt_and_write(new_cred_template, 4)
                        print("New credential saved successfully!")
                    else:
                        print("Account for {0} already exits".format(account))
                    ### End Add new Credential ###
                elif user_input == 2:
                    ### Start Get new Credential ###
                    account = get_user_input("Enter Account Name: ")
                    cred = get_credential_for_account(account)
                    if (cred is None):
                        print("Credential not found for account {0}".format(
                            account))
                    else:
                        print(cred)
                    ### End Get new Credential ###
                elif user_input == 3:
                    ### Start Update Credential ###
                    account = get_user_input("Enter Account Name: ")
                    credential_list = get_raw_credential_for_account(account)
                    if credential_list[-1] is None:
                        print("Account for {0} does not exits".format(account))
                    else:
                        is_password_updated = update_credential_for_account(
                            account, credential_list[0], credential_list[1])
                        if is_password_updated:
                            print("Credentials updated successfully!")
                    ### End Update Credential ###
                else:
                    ### Start Delete Credential ###
                    account = get_user_input("Enter Account Name: ")
                    credential_list = get_raw_credential_for_account(account)
                    if credential_list[-1] is None:
                        print("Account for {0} does not exits".format(account))
                    else:
                        print(credential_list)
                        is_password_deleted = delete_credential_for_account(
                            credential_list[0], credential_list[1])
                        if is_password_deleted:
                            print("Credentials deleted successfully!")
                    ### End Delete Credential ###
        else:
            print("Invalid User input, Try again!")


if __name__ == "__main__":
    main()
