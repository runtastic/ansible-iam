#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule

import json
import time
from googleapiclient.discovery import build
from google.oauth2 import service_account

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['production'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: gsuite_user

short_description: Managing Google G Suite users

version_added: "2.8"

description:
    - "With this module you can create, modify, disable and delete Google G Suite users and add them to groups."

options:
    google_private_key:
        description:
            - The private key to authenticate to the Google API. Create it for your service account: https://console.cloud.google.com/projectselector2/iam-admin/serviceaccounts?supportedpurview=project
        required: true
    google_subject:
        description:
            - The email address of the account you want to impersonate. Google is a bit fishy here: https://stackoverflow.com/questions/60262432/service-account-not-authorized-to-access-this-resource-api-while-trying-to-acces/60262433#60262433
        required: true
    email:
        description:
            - The email of the user (unique)
        required: true
    familyName:
        description:
            - The family name of the user
        required: true
    givenName:
        description:
            - The given name of the user
        required: true
    employeeId:
        description:
            - The employee ID of the user
        required: true
    password:
        description:
            - The password of the user
        required: false
    changePasswordAtNextLogin:
        description:
            - Set to true if user should have to change his password the next time he logs in
        required: false
    groups:
        description:
            - A dictionary of groups where the user should be part of
        required: false
    aliases:
        description:
            - A list of alias email addresses
        required: false
    suspended:
        description:
            - Set the user suspended
        required: false
    orgUnitPath:
        description:
            - Set the user Organisational Unit Path
        required: false
    transferUserEmail:
        description:
            - Email address of user to which data should be transfered on deletion. Leave empty for no transfer.
        required: false
    state:
        description:
            - Default is 'present'. If 'absent' user will be deleted.
        required: false

extends_documentation_fragment:
    - gsuite

author:
    - Peter Loeffler (peter.loeffler@guruz.at)
'''

EXAMPLES = '''
- name: G Suite user john.doe@example.com
  gsuite_user:
    google_private_key: '{"type":"service_account","project_id":"YOUR_PROJECT_ID","private_key_id":"YOUR_PRIVATE_KEY_ID","private_key":"-----BEGIN PRIVATE KEY-----\nxxxxx\nyyyyy\n-----END PRIVATE KEY-----\n","client_email":"YOUR_CLIENT_EMAIL","client_id":"YOUR_CLIENT_ID","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"YOUR_CLIENT_X509_CERT_URL"}'
    google_subject: 'admin@example.com'
    email: 'john.doe@example.com'
    familyName: 'Doe'
    givenName: 'John'
    password: 'Secr3t!'
    changePasswordAtNextLogin: true
    orgUnitPath: '/Employees'
    aliases:
      - webmaster@example.com
      - admin@example.com
    groups:
      team:
        groupKey: 'team@example.com'
        role: 'MEMBER'
      admin:
        groupKey: 'admin@example.com'
        role: 'OWNER'
    suspended: false
    state: present
'''

RETURN = '''
changed:
    description: Returns if anything has changed
    type: boolean
    returned: always
success:
    description: Returns if this module was successful
    type: boolean
    returned: always
user_insert:
    description: Information about inserting the user
    type: dict
    returned: always
user_patch:
    description: Information about patching the user
    type: dict
    returned: always
user_delete:
    description: Information about deleting the user
    type: dict
    returned: always
manage_groups:
    description: Information about the group memberships
    type: dict
    returned: always
aliases_insert:
    description: Information about the aliases
    type: list
    returned: always
'''

SCOPES = [
    'https://www.googleapis.com/auth/admin.directory.user',
    'https://www.googleapis.com/auth/admin.directory.group',
    'https://www.googleapis.com/auth/admin.datatransfer',
]


def google_directory(privateKey, subject):
    creds = service_account.Credentials.from_service_account_info(
        privateKey, scopes=SCOPES, subject=subject
    )
    service = build('admin', 'directory_v1', credentials=creds)
    return service


def google_datatransfer(privateKey, subject):
    creds = service_account.Credentials.from_service_account_info(
        privateKey, scopes=SCOPES, subject=subject
    )
    service = build('admin', 'datatransfer_v1', credentials=creds)
    return service


def user_get(module, gDirectory, email):
    success = False
    message = ""

    try:
        # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_directory_v1.users.html#get
        #
        # this raises googleapiclient.errors.HttpError if userKey does not
        # exist:
        user = gDirectory.users().get(userKey=email).execute()

        # find out the primary email of the user
        # in Ruby this would be `user.find { |e| e['primary'] }['address']` :~)
        primary_email = list(
            filter(lambda e: 'primary' in e, user['emails'])
        )[0]['address']

        if primary_email.lower() == email.lower():
            success = True
            message = f"User existing: {email}"
        else:
            # to avoid surprises fail if the email provided is NOT the primary email
            module.fail_json(
                msg=f"User exists, but {email} is an alias for {primary_email}"
            )
    except Exception as e:
        success = False
        message = f"User NOT existing: {email} ({e})"

    return success, message


def user_insert(gDirectory, email, givenName, familyName, employeeId, password,
                changePasswordAtNextLogin, suspended, orgUnitPath):
    success = False
    message = ""

    userInsert = {
        "primaryEmail": email,
        "externalIds": [
            {"value": employeeId, "type": "organization"}
        ],
        "password": password,
        "changePasswordAtNextLogin": changePasswordAtNextLogin,
        "suspended": suspended,
        "orgUnitPath": orgUnitPath,
        "name": {
            "givenName": givenName,
            "familyName": familyName
        }
    }

    try:
        # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_directory_v1.users.html#insert
        gDirectory.users().insert(body=userInsert).execute()
        success = True
        message = f"User created: {email}"
    except Exception as e:
        success = False
        message = f"ERROR creating user {email}: {e}"

    return success, message


def user_patch(gDirectory, email, givenName, familyName, employeeId, password,
               suspended, orgUnitPath):
    success = False
    message = ""

    userPatch = {
        "primaryEmail": email,
        "externalIds": [
            {"value": employeeId, "type": "organization"}
        ],
        "name": {
            "givenName": givenName,
            "familyName": familyName
        },
        "orgUnitPath": orgUnitPath,
        "suspended": suspended
    }

    try:
        # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_directory_v1.users.html#patch
        gDirectory.users().patch(userKey=email, body=userPatch).execute()
        success = True
        message = f"User modified: {email}"
    except Exception as e:
        success = False
        message = f"ERROR modifying user {email}: {e}"

    return success, message


def user_get_id(gDirectory, email):
    uid = gDirectory.users().get(userKey=email).execute()['id']
    return uid


def user_delete(module, gDirectory, gDatatransfer, email, transfer_user):
    success = False
    message = ""
    delete_user = False

    if transfer_user != "":
        try:
            # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_directory_v1.users.html#patch
            gDirectory.users().patch(
                userKey=email, body={"suspended": True}
            ).execute()
            success = True
            message = f"User {email} suspended."
        except Exception as e:
            module.fail_json(msg=f"ERROR while suspending user {email}: {e}")

        try:
            # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_datatransfer_v1.applications.html#list
            applications = gDatatransfer.applications().list() \
                .execute()['applications']
            success = True
        except Exception as e:
            module.fail_json(
                msg=f"ERROR could not get apps for data transfer: {e}"
            )

        transfers = []
        i = 0
        for application in applications:
            app_name = application['name']
            if app_name == "Drive and Docs" or app_name == "Calendar":
                transfers.append({"applicationId": application['id']})
                try:
                    transfers[i]['applicationTransferParams'] = [
                        application['transferParams'][0]
                    ]
                except Exception:
                    pass
                i = i + 1

        try:
            # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_datatransfer_v1.transfers.html#insert
            t = gDatatransfer.transfers().insert(
                body={
                    "oldOwnerUserId": user_get_id(gDirectory, email),
                    "newOwnerUserId": user_get_id(gDirectory, transfer_user),
                    "applicationDataTransfers": transfers
                }
            ).execute()
            success = True
            message += f" Datatransfer from {email} to {transfer_user}" \
                + " initiated."
        except Exception as e:
            module.fail_json(
                msg=f"ERROR while initiating data transfer from {email} to "
                    + f"{transfer_user}: {e}"
            )

        try:
            # wait until datatransfer is successful
            #
            # there is no documentation on what values this
            # `overallTransferStatusCode` might have.
            #
            # so far I've seen:
            #   - 'inProgress' -> data transfer is currently in progress
            #   - 'completed'  -> data transfer is complete
            #
            # therefore fail on every other status code we get back
            #
            # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_datatransfer_v1.transfers.html#get
            code = gDatatransfer.transfers().get(dataTransferId=t['id']) \
                .execute()['overallTransferStatusCode']
            while code.lower() == 'inprogress':
                time.sleep(5)
                code = gDatatransfer.transfers().get(dataTransferId=t['id']) \
                    .execute()['overallTransferStatusCode']

            if code.lower() != 'completed':
                module.fail_json(msg=f"Data transfer failed ({code})")

            success = True
            delete_user = True  # the user is safe to delete now
            message += f" Datatransfer from {email} to {transfer_user}" \
                + " completed."
        except Exception as e:
            module.fail_json(
                msg=f"ERROR while transferring data from {email} to "
                    + f"{transfer_user}: {e}"
            )
    else:
        # no transfer_user specified --> always delete the user
        delete_user = True

    if delete_user is True:
        try:
            # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_directory_v1.users.html#delete
            gDirectory.users().delete(userKey=email).execute()
            success = True
            message += f" User deleted: {email}"
        except Exception as e:
            module.fail_json(msg=f"ERROR while deleting user {email}: {e}")

    return success, message


def manage_groups(module, gDirectory, email, groups):
    # find user's group memberships
    current_groups = []
    try:
        # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_directory_v1.groups.html#list
        groups_list_response = gDirectory.groups().list(userKey=email).execute()
        if 'groups' in groups_list_response:
            for group in groups_list_response['groups']:
                # get group member properties
                # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_directory_v1.members.html#get
                member_properties = gDirectory.members().get(
                    groupKey=group['email'],
                    memberKey=email
                ).execute()
                current_groups.append({
                    'groupKey': group['email'],
                    'role': member_properties['role']
                })
    except Exception as e:
        module.fail_json(
            msg=f"ERROR while finding group memberships for {email}: {e}"
        )

    # figure out groups to be removed
    groups_list = groups.values()  # groups are passed in as a dict, but we really only care about the values
    # only get the emails for easier comparison (also for deletion the `role` does not matter)
    groups_list_emails = [group['groupKey'] for group in groups_list]
    current_group_emails = [group['groupKey'] for group in current_groups]
    groups_del = [group for group in current_group_emails if group not in groups_list_emails]

    results = {}

    # remove the user from the groups
    for group_key in groups_del:
        try:
            # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_directory_v1.members.html#delete
            gDirectory.members().delete(
                groupKey=group_key, memberKey=email
            ).execute()

            results.update({
                group_key: {
                    'success': True,
                    'message': f"User {email} removed from group {group_key}"
                }
            })
        except Exception as e:
            module.fail_json(
                msg=f"ERROR while removing {email} from group {group_key}: {e}"
            )

    for group in groups_list:
        group_key = group['groupKey']
        role = group['role']
        is_member = False

        try:
            # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_directory_v1.members.html#hasMember
            has_member_response = gDirectory.members().hasMember(
                groupKey=group_key, memberKey=email
            ).execute()
            if has_member_response['isMember']:
                is_member = True
                results.update({
                    group_key: {
                        'success': True,
                        'message': f"User {email} is already a member of"
                                   + f" {group_key}"
                    }
                })
        except Exception:
            pass  # assume user is not in group

        if is_member:  # a member --> update group member (because of role)
            try:
                # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_directory_v1.members.html#update
                gDirectory.members().update(
                    groupKey=group_key, memberKey=email, body={
                        "role": role
                    }
                ).execute()

                results.update({
                    group_key: {
                        'success': True,
                        'message': f"Updated membership of {email} in group"
                                   + f" {group_key}"
                    }
                })
            except Exception as e:
                module.fail_json(
                    msg=f"ERROR while updating membership of {email} in group "
                        + f"{group_key}: {e}"
                )
        else:  # not a member --> insert new group member
            try:
                # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_directory_v1.members.html#insert
                gDirectory.members().insert(
                    groupKey=group_key, body={
                        "email": email,
                        "role": role
                    }
                ).execute()

                results.update({
                    group_key: {
                        'success': True,
                        'message': f"User {email} added to group {group_key}"
                    }
                })
            except Exception as e:
                module.fail_json(
                    msg=f"ERROR while adding {email} to group {group_key}: {e}"
                )

    return results


def aliases_insert(gDirectory, email, aliases):
    results = {}

    try:
        # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_directory_v1.users.aliases.html#list
        aliasesExisting = gDirectory.users().aliases().list(userKey=email) \
            .execute()["aliases"]
    except Exception:
        aliasesExisting = False

    for alias in aliases:
        aliasExists = False
        if aliasesExisting is not False:
            for checkAlias in aliasesExisting:
                if checkAlias["alias"] == alias:
                    aliasExists = True

        if aliasExists is True:
            results.update({
                alias: {
                    'success': True,
                    'message': f"Alias {alias} already exists for user {email}"
                }
            })
        else:
            try:
                # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_directory_v1.users.aliases.html#insert
                gDirectory.users().aliases().insert(
                    userKey=email,
                    body={"alias": alias}
                ).execute()
                results.update({
                    alias: {
                        'success': True,
                        'message': f"Alias {alias} created for user {email}"
                    }
                })
            except Exception as e:
                results.update({
                    alias: {
                        'success': False,
                        'message': f"ERROR creating alias {alias} for user"
                                   + f" {email}: {e}"
                    }
                })

    return results


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        google_private_key=dict(type='json', required=True),
        google_subject=dict(type='str', required=True),
        email=dict(type='str', required=True),
        givenName=dict(type='str', required=True),
        familyName=dict(type='str', required=True),
        employeeId=dict(type='str', required=True),
        password=dict(type='str', required=False,
                      default='change.this.password.now!', no_log=True),
        changePasswordAtNextLogin=dict(type='bool', required=False,
                                       default=True),
        aliases=dict(type='list', required=False, default=list()),
        groups=dict(
            type='dict',
            required=False,
            groupKey=dict(type='str', required=True),
            role=dict(type='str', required=True),
            default=dict()
        ),
        suspended=dict(type='bool', required=False, default=False),
        orgUnitPath=dict(type='str', required=False, default='/'),
        transferUserEmail=dict(type='str', required=False, default=''),
        state=dict(choices=['present', 'absent'], default='present')
    )

    # seed the result dict in the object
    # we primarily care about changed and state
    # change is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
        success=False,
        user_insert=dict(success=False, message='Not executed'),
        user_patch=dict(success=False, message='Not executed'),
        user_delete=dict(success=False, message='Not executed'),
        aliases_insert=dict(success=False, message='Not executed'),
        manage_groups=dict(
            group=dict(success=False, message='Not executed')
        )
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        module.exit_json(**result)

    # manipulate or modify the state as needed (this is going to be the
    # part where your module will do what it needs to do)
    g_private_key = json.loads(module.params['google_private_key'])
    g_subject = module.params['google_subject']
    gDirectory = google_directory(g_private_key, g_subject)
    gDatatransfer = google_datatransfer(g_private_key, g_subject)

    try:
        user_exists, _ = user_get(module, gDirectory, module.params['email'])
        result['success'] = user_exists
    except Exception as e:
        module.fail_json(msg=f'Failed to check user existence: {e}', **result)

    if module.params['state'] == 'absent':
        if user_exists:  # user exists and state is absent -> delete them
            try:
                user_del_success, user_del_message = user_delete(
                    module,
                    gDirectory,
                    gDatatransfer,
                    module.params['email'],
                    module.params['transferUserEmail']
                )
                result['user_delete']['success'] = user_del_success
                result['user_delete']['message'] = user_del_message
                result['success'] = user_del_success
            except Exception as e:
                module.fail_json(msg=f'Failed to delete user: {e}', **result)
    else:
        if user_exists:  # user exists -> update them
            try:
                user_patch_success, user_patch_message = user_patch(
                    gDirectory,
                    module.params['email'],
                    module.params['givenName'],
                    module.params['familyName'],
                    module.params['employeeId'],
                    module.params['password'],
                    module.params['suspended'],
                    module.params['orgUnitPath']
                )
                result['user_patch']['success'] = user_patch_success
                result['user_patch']['message'] = user_patch_message
                result['success'] = user_patch_success
            except Exception as e:
                module.fail_json(msg=f'Failed to patch user: {e}', **result)
        else:  # user does not exist -> create them
            try:
                user_insert_success, user_insert_message = user_insert(
                    gDirectory,
                    module.params['email'],
                    module.params['givenName'],
                    module.params['familyName'],
                    module.params['employeeId'],
                    module.params['password'],
                    module.params['changePasswordAtNextLogin'],
                    module.params['suspended'],
                    module.params['orgUnitPath']
                )
                result['user_insert']['success'] = user_insert_success
                result['user_insert']['message'] = user_insert_message
                result['success'] = user_insert_success
            except Exception as e:
                module.fail_json(msg=f'Failed to insert user: {e}', **result)

        try:  # at this point the user exists -> manage their groups
            result['manage_groups'] = manage_groups(
                module,
                gDirectory,
                module.params['email'],
                module.params['groups']
            )
            result['success'] = True
        except Exception as e:
            module.fail_json(
                msg=f'Failed to add user to groups: {e}', **result
            )

        try:  # at this point the user exists -> add new mail aliases
            result['aliases_insert'] = aliases_insert(
                gDirectory,
                module.params['email'],
                module.params['aliases']
            )
            result['success'] = True
        except Exception as e:
            module.fail_json(
                msg=f'Failed create aliases for user: {e}',
                **result
            )

    # use whatever logic you need to determine whether or not this module
    # made any modifications to your target
    if result['success']:
        result['changed'] = True

    # during the execution of the module, if there is an exception or a
    # conditional state that effectively causes a failure, run
    # AnsibleModule.fail_json() to pass in the message and the result
    # example:
    # if module.params['email'] == 'fail me':
    #     module.fail_json(msg='You requested this to fail', **result)

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
