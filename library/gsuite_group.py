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
module: gsuite_group

short_description: Managing Google G Suite groups

version_added: "2.8"

description:
  - "With this module you can create, modify, disable and delete Google G Suite groups."

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
      - The email of the group (unique)
    required: true
  name:
    description:
      - The name of the group
    required: true
  description:
    description:
      - The description of the group
    required: true
  aliases:
    description:
      - A list of alias email addresses
    required: false
  group_settings:
    description:
      - Group settings to set.  See https://developers.google.com/admin-sdk/groups-settings/v1/reference/groups for more information.
      - Defaults to `{ }`
    required: false
  state:
    description:
      - Default is 'present'. If 'absent' user will be deleted.
    required: false

extends_documentation_fragment:
  - gsuite

author:
  - Georg Gadinger (georg.gadinger@runtastic.com)
'''

EXAMPLES = '''
- name: Manage GSuite group
  gsuite_user:
    google_private_key: '{"type":"service_account","project_id":"YOUR_PROJECT_ID","private_key_id":"YOUR_PRIVATE_KEY_ID","private_key":"-----BEGIN PRIVATE KEY-----\nxxxxx\nyyyyy\n-----END PRIVATE KEY-----\n","client_email":"YOUR_CLIENT_EMAIL","client_id":"YOUR_CLIENT_ID","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"YOUR_CLIENT_X509_CERT_URL"}'
    google_subject: 'admin@example.com'
    name: 'Some Group'
    email: 'somegroup@example.com'
    description: 'This is some group for testing'
    group_settings:
      whoCanViewGroup: "ALL_IN_DOMAIN_CAN_VIEW"
      whoCanViewMembership: "ALL_IN_DOMAIN_CAN_VIEW"
      whoCanPostMessage: "ALL_IN_DOMAIN_CAN_POST"
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
group_insert:
  description: Information about inserting the group
  type: dict
  returned: always
group_patch:
  description: Information about patching the group
  type: dict
  returned: always
group_delete:
  description: Information about deleting the group
  type: dict
  returned: always
'''

SCOPES = {
    'directory': [
        'https://www.googleapis.com/auth/admin.directory.group',
    ],
    'groups_settings': [
        'https://www.googleapis.com/auth/apps.groups.settings',
    ]
}


def google_directory(privateKey, subject):
    creds = service_account.Credentials.from_service_account_info(
        privateKey, scopes=SCOPES['directory'], subject=subject
    )
    service = build('admin', 'directory_v1', credentials=creds)
    return service


def google_groups_settings(privateKey, subject):
    creds = service_account.Credentials.from_service_account_info(
        privateKey, scopes=SCOPES['groups_settings'], subject=subject
    )
    service = build('groupssettings', 'v1', credentials=creds)
    return service


def group_get(module, gDirectory, email):
    success = False
    message = ""

    try:
        # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_directory_v1.groups.html#get
        #
        # this raises googleapiclient.errors.HttpError if groupKey does not
        # exist:
        group = gDirectory.groups().get(groupKey=email).execute()

        # ensure we have the real email and not an alias
        primary_email = group['email']
        if primary_email.lower() == email.lower():
            success = True
            message = f"Group exists: {email}"
        else:
            # to avoid surprises fail if the email provided is NOT the primary email
            module.fail_json(
                msg=f"Group exists, but {email} is an alias for "
                    + f"{primary_email}"
            )
    except Exception as e:
        success = False
        message = f"Group does NOT exist: {email} ({e})"

    return success, message


def group_insert(module, gDirectory, email, name, description):
    changed = False
    message = ""

    groupInsert = {
        "email": email,
        "name": name,
        "description": description,
    }

    try:
        # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_directory_v1.groups.html#insert
        gDirectory.groups().insert(body=groupInsert).execute()
        changed = True
        message = f"Group created: {email}"
    except Exception as e:
        module.fail_json(msg=f"ERROR creating group {email}: {e}")

    return True, changed, message


def group_patch(module, gDirectory, email, name, description):
    changed = False
    message = ""

    groupPatch = {
        "email": email,
        "name": name,
        "description": description,
    }

    try:
        # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_directory_v1.groups.html#patch
        gDirectory.groups().patch(groupKey=email, body=groupPatch).execute()

        # FIXME: ideally this should be only True if it was really changed
        changed = True
        message = f"Group modified: {email}"
    except Exception as e:
        module.fail_json(msg=f"ERROR modifying group {email}: {e}")

    return True, changed, message


def group_delete(module, gDirectory, email):
    changed = False
    message = ""

    try:
        # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_directory_v1.groups.html#delete
        gDirectory.groups().delete(groupKey=email).execute()
        changed = True
        message = f"Group deleted: {email}"
    except Exception as e:
        module.fail_json(msg=f"ERROR while deleting group {email}: {e}")

    return True, changed, message


def aliases_upsert(module, gDirectory, email, aliases):
    """
    This method should not have to exist.

    Both groups().insert(...) and groups.patch(...) from the docs for the
    Python library mention a parameter "aliases" you can pass in to the request
    body:
    https://googleapis.github.io/google-api-python-client/docs/dyn/admin_directory_v1.groups.html#patch

    The REST API reference for the same endpoints say that the request body
    "contains an instance of Group" ...:
    https://developers.google.com/admin-sdk/directory/reference/rest/v1/groups/patch
    ...which also features an "aliases" parameter:
    https://developers.google.com/admin-sdk/directory/reference/rest/v1/groups#Group

    Both these parameters seem to accept a List of String.  However, neither
    groups().insert(...) nor groups().patch(...) appear to do anything when
    a string is passed to it.  At least any existing aliases are returned as a
    List of String.

    And then there's this mess of a tutorial / guide:
    https://developers.google.com/admin-sdk/directory/v1/guides/manage-groups
    which claims the "aliases" field returned looks like this:
        "aliases": [
            {
                "alias": "best_sales_group@example.com"
            }
        ]
    This is completely inconsistent with the API reference docs.  At least it
    mentions that you have to use another endpoint to modify the aliases, but
    from that doc it's not entirely clear how...

    """
    changed = False
    message = "Aliases are up to date."

    existing_aliases = []

    try:
        # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_directory_v1.groups.aliases.html#list
        response = gDirectory.groups().aliases().list(groupKey=email).execute()
        # Ruby: `response["aliases"].map { |obj| obj["alias"] }`
        existing_aliases = [obj["alias"] for obj in response["aliases"]]
    except Exception:
        pass  # existing_aliases is already initialized as []

    # Calculate the difference between lists
    aliases_to_be_added = \
        [alias for alias in aliases if alias not in existing_aliases]
    aliases_to_be_removed = \
        [alias for alias in existing_aliases if alias not in aliases]

    for alias in aliases_to_be_added:
        try:
            # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_directory_v1.groups.aliases.html#insert
            gDirectory.groups().aliases().insert(
                groupKey=email,
                body={"alias": alias}
            ).execute()
            changed = True
        except Exception as e:
            module.fail_json(
                msg=f"ERROR adding alias {alias} to group {email}: {e}"
            )

    for alias in aliases_to_be_removed:
        try:
            # https://googleapis.github.io/google-api-python-client/docs/dyn/admin_directory_v1.groups.aliases.html#delete
            gDirectory.groups().aliases().delete(
                groupKey=email,
                alias=alias
            ).execute()
            changed = True
        except Exception as e:
            module.fail_json(
                msg=f"ERROR removing alias {alias} from group {email}: {e}"
            )

    if changed:
        message = f"Aliases updated (added: {aliases_to_be_added}, " \
            + f"removed: {aliases_to_be_removed})"

    return True, changed, message


def groups_settings_update(module, gGroupsSettings, email, group_settings):
    changed = False
    message = "Didn't touch the group settings."

    # these should be changed via other means, not by group_settings; or just
    # don't make sense here
    keys_to_exclude = {'email', 'description', 'kind', 'name'}
    body = {k:v for k,v in iter(group_settings.items()) if k not in keys_to_exclude}

    if not body:  # you have to read this as: "if body is empty:"
        # no need to change anything
        return True, changed, message

    try:
        # https://googleapis.github.io/google-api-python-client/docs/dyn/groupssettings_v1.groups.html#patch
        gGroupsSettings.groups().patch(
            groupUniqueId=email,
            body=body,
        ).execute()
        changed = True
        message = f"Group settings updated: {email}"
    except Exception as e:
        module.fail_json(
            msg=f"ERROR updating group settings for group {email}: {e}"
        )

    return True, changed, message

def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        google_private_key=dict(type='json', required=True),
        google_subject=dict(type='str', required=True),
        email=dict(type='str', required=True),
        name=dict(type='str', required=True),
        description=dict(type='str', required=True),
        aliases=dict(type='list', required=False, default=list()),
        group_settings=dict(type='dict', required=False, default={}),
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
        group_insert=dict(
            success=False, changed=False, message='Not executed'),
        group_patch=dict(
            success=False, changed=False, message='Not executed'),
        group_delete=dict(
            success=False, changed=False, message='Not executed'),
        aliases_upsert=dict(
            success=False, changed=False, message='Not executed'),
        groups_settings_update=dict(
            success=False, changed=False, message='Not executed'),
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
    gGroupsSettings = google_groups_settings(g_private_key, g_subject)

    try:
        group_exists, _ = group_get(module, gDirectory, module.params['email'])
        result['success'] = group_exists
    except Exception as e:
        module.fail_json(msg=f'Failed to check group existence: {e}', **result)

    if module.params['state'] == 'absent':
        if group_exists:  # group exists and state is absent -> delete them
            group_del_success, group_del_changed, \
                group_del_message = group_delete(
                    module,
                    gDirectory,
                    module.params['email']
                )
            result['group_delete']['success'] = group_del_success
            result['group_delete']['changed'] = group_del_changed
            result['group_delete']['message'] = group_del_message
            result['success'] = group_del_success
            result['changed'] = result['changed'] or group_del_changed
    else:
        if group_exists:  # group exists -> update them
            group_patch_success, group_patch_changed, \
                group_patch_message = group_patch(
                    module,
                    gDirectory,
                    module.params['email'],
                    module.params['name'],
                    module.params['description']
                )
            result['group_patch']['success'] = group_patch_success
            result['group_patch']['changed'] = group_patch_changed
            result['group_patch']['message'] = group_patch_message
            result['success'] = group_patch_success
            result['changed'] = result['changed'] or group_patch_changed
        else:  # group does not exist -> create them
            group_insert_success, group_insert_changed, \
                group_insert_message = group_insert(
                    module,
                    gDirectory,
                    module.params['email'],
                    module.params['name'],
                    module.params['description']
                )
            result['group_insert']['success'] = group_insert_success
            result['group_insert']['changed'] = group_insert_changed
            result['group_insert']['message'] = group_insert_message
            result['success'] = group_insert_success
            result['changed'] = result['changed'] or group_insert_changed

        ########################################################
        # at this point the group exists -> add new mail aliases
        aliases_upsert_success, aliases_upsert_changed, \
            aliases_upsert_message = aliases_upsert(
                module,
                gDirectory,
                module.params['email'],
                module.params['aliases']
            )
        result['aliases_upsert']['success'] = aliases_upsert_success
        result['aliases_upsert']['changed'] = aliases_upsert_changed
        result['aliases_upsert']['message'] = aliases_upsert_message
        result['success'] = aliases_upsert_success
        result['changed'] = result['changed'] or aliases_upsert_changed

        # update group settings
        groups_settings_update_success, groups_settings_update_changed, \
            groups_settings_update_message = groups_settings_update(
                module,
                gGroupsSettings,
                module.params['email'],
                module.params['group_settings']
            )
        result['groups_settings_update']['success'] = groups_settings_update_success
        result['groups_settings_update']['changed'] = groups_settings_update_changed
        result['groups_settings_update']['message'] = groups_settings_update_message
        result['success'] = groups_settings_update_success
        result['changed'] = result['changed'] or groups_settings_update_changed

    # at this point result['changed'] reflects whether anything has changed

    result['success'] = True  # this module is done at this point 🎉
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
