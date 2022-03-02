#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url

import json
import time
import urllib.parse # quote

ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['production'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: scim_user

short_description: Manage SCIM users

version_added: "4.0"

description:
  - "This module is used to manage users at external services via SCIM."

options:
  base_url:
    description:
      - The base url for accessing a service's SCIM API.
    required: true
  authorization:
    description:
      - Contents of the `Authorization` header.
    required: true
  givenName:
    description:
      - The given name of a user.
    required: true
  familyName:
    description:
      - The family name of a user.
    required: true
  userName:
    description:
      - An unique identifier of a user.
    required: true
  email:
    description:
      - The email address for a user.
    required: true
  update:
    description:
      - Whether the user should be updated if they already exist.
      - Default is 'true'.
    required: false
  active:
    description:
      - Whether the user should be active.
      - Default is 'true'.
    required: false
  scim_version:
    description:
      - Enable compatibility with newer SCIM versions.
      - Default is 'v1'.
    required: false
  extra_attributes:
    description:
      - Additional attributes to pass in to the creation/update request of a user.
    required: false
  search_query:
    description:
      - The search query used to find the user, e.g. `email Eq "fritzfantom@example.com"`.
    required: true
  state:
    description:
      - Default is 'present'. If 'absent' user will be deleted.
    required: false

author:
  - Georg Gadinger (georg.gadinger@runtastic.com)
'''

EXAMPLES = '''
- name: Manage Slack user (via SCIM)
  scim_user:
    base_url: "https://api.slack.com/scim/v1"
    authorization: "Bearer {{ slack_api_token }}"

    givenName: "Fritz"
    familyName: "Fantom"
    userName: "frf"
    email: "fritz.fantom@runtastic.com"
    extra_attributes:
      nickName: "frf"
      profileUrl: "https://runtastic.slack.com/team/frf"
      timezone: "Europe/Vienna"

    # query used to find the user
    search_query: 'email Eq "fritz.fantom@runtastic.com"'

    # do not update the user, only create/delete them
    update: no

    # Slack can not delete any users, only deactivate them.  So instead of
    # setting `state: absent`, you would need to do this:
    active: no

    state: present

- name: Manage Miro user (via SCIM)
  scim_user:
    base_url: "https://miro.com/api/v1/scim"
    authorization: "Bearer {{ miro_api_token }}"
    scim_version: 'v2'

    givenName: "Fritz"
    familyName: "Fantom"
    userName: "fritz.fantom@runtastic.com"
    email: "fritz.fantom@runtastic.com"

    extra_attributes:
      # assign the Full license to the user
      userType: 'Full'

    # query used to find the user
    search_query: 'userName eq "fritz.fantom@runtastic.com"'

    active: yes

    state: present

- name: Manage AWS user (via SCIM)
  scim_user:
    base_url: "https://scim.eu-west-1.amazonaws.com/foobar/scim/v2"
    authorization: "Bearer {{ aws_api_token }}"

    givenName: "Fritz"
    familyName: "Fantom"
    userName: "fritz.fantom@runtastic.com"
    email: "fritz.fantom@runtastic.com"

    # query used to find the user
    search_query: 'userName eq "fritz.fantom@runtastic.com"'

    state: present
'''

RETURN = '''
changed:
    description: Returns if anything has changed
    type: boolean
    returned: always
user_id:
    description: External ID of the user
    type: boolean
    returned: when the user exists on the external system
exists:
    description: Whether the user exists on the external system **and is active**
    type: boolean
    returned: always
created:
    description: Whether the user got created
    type: boolean
    returned: always
activated:
    description: Whether the user got activated on the external system
    type: boolean
    returned: always
deactivated:
    description: Whether the user got deactivated on the external system
    type: boolean
    returned: always
updated:
    description: Whether the user got updated
    type: boolean
    returned: always
deleted:
    description: Whether the user got deleted
    type: boolean
    returned: always
'''


def find_user(module, base_url, default_headers):
    search_query = urllib.parse.quote(module.params['search_query'])

    resp, info = fetch_url(
        module,
        f"{base_url}/Users?filter={search_query}",
        headers=default_headers,
    )

    body = json.loads(resp.read())

    if (not 'Resources' in body) or (len(body['Resources']) == 0):
        # no user found for the query
        return None, False

    user = body['Resources'][0]

    return user['id'], user['active']


def user_body(module):
    given_name       = module.params['givenName']
    family_name      = module.params['familyName']
    user_name        = module.params['userName']
    email            = module.params['email']
    extra_attributes = module.params['extra_attributes']

    display_name = f"{given_name} {family_name}"

    base_body = {
        'userName': user_name,
        'name': {
            'familyName': family_name,
            'givenName': given_name,
        },
        'displayName': display_name,
        'emails': [
            {
                'value': email,
                'type': 'work',
                'primary': True,
            },
        ],
        'active': True,
    }

    return {**base_body, **extra_attributes}  # merge two dicts together


def create_user(module, base_url, default_headers):
    use_scim_v2 = module.params['scim_version'] == 'v2'
    schemas = []

    if use_scim_v2:
        pass # TODO: figure out which schema ot use
    else:
        schemas = [
            'urn:scim:schemas:core:1.0',
        ]

    body = {**user_body(module), 'schemas': schemas}

    resp, info = fetch_url(
        module,
        f"{base_url}/Users",
        headers=default_headers,
        method='POST',
        data=module.jsonify(body),
    )

    status_code = info['status']
    if status_code not in range(200, 300):
        module.fail_json(
            msg=f"create failed: received status {status_code}, expected 2xx",
            info=info,
        )

    response = json.loads(resp.read())

    return response['id']


def activate_user(module, base_url, default_headers, user_id, active=True):
    use_scim_v2 = module.params['scim_version'] == 'v2'

    if use_scim_v2:
        body = {
            'schemas': [
                'urn:ietf:params:scim:api:messages:2.0:PatchOp',
            ],
            'Operations': [
                {
                    'op': 'Replace',
                    'path': 'active',
                    'value': active,
                },
            ],
        }
    else:
        body = {
            'schemas': [
                'urn:scim:schemas:core:1.0',
            ],
            'active': active
        }

    resp, info = fetch_url(
        module,
        f"{base_url}/Users/{user_id}",
        headers=default_headers,
        method='PATCH',
        data=module.jsonify(body),
    )

    status_code = info['status']
    if status_code not in range(200, 300):
        action = "activate" if active else "deactivate"
        module.fail_json(
            msg=f"{action} failed: received status {status_code}, expected 2xx",
            info=info,
        )

    return True


def update_user(module, base_url, default_headers, user_id):
    body = {**user_body(module), 'id': user_id}

    resp, info = fetch_url(
        module,
        f"{base_url}/Users/{user_id}",
        headers=default_headers,
        method='PUT',
        data=module.jsonify(body),
    )

    status_code = info['status']
    if status_code not in range(200, 300):
        module.fail_json(
            msg=f"update failed: received status {status_code}, expected 2xx",
            info=info,
            request=body
        )

    return True


def delete_user(module, base_url, default_headers, user_id):
    resp, info = fetch_url(
        module,
        f"{base_url}/Users/{user_id}",
        headers=default_headers,
        method='DELETE',
    )

    status_code = info['status']
    if status_code not in range(200, 300):
        module.fail_json(
            msg=f"delete failed: received status {status_code}, expected 2xx",
            info=info
        )

    return True


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        base_url=dict(type='str', required=True),
        authorization=dict(type='str', required=True),
        givenName=dict(type='str', required=True),
        familyName=dict(type='str', required=True),
        userName=dict(type='str', required=True),
        email=dict(type='str', required=True),
        update=dict(type='bool', required=False, default=True),
        active=dict(type='bool', required=False, default=True),
        scim_version=dict(type='str', required=False, default='v1', choices=['v1', 'v2']),
        extra_attributes=dict(type='dict', required=False, default=dict()),
        search_query=dict(type='str', required=True),
        state=dict(choices=['present', 'absent'], default='present')
    )

    # seed the result dict in the object
    # we primarily care about changed and state
    # change is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,

        exists=False,

        created=False,
        activated=False,
        deactivated=False,
        updated=False,
        deleted=False,
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=False
    )

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        module.exit_json(**result)

    # manipulate or modify the state as needed (this is going to be the
    # part where your module will do what it needs to do)

    # vars for easier usage
    base_url = module.params['base_url']
    default_headers = {
        'Authorization': module.params['authorization'],
        'Content-Type': 'application/json',
    }
    should_be_present = module.params['state'] != 'absent'
    should_update_user = module.params['update']
    should_be_active = module.params['active']

    user_id, user_active = find_user(module, base_url, default_headers)
    if user_id is None:
        # no user found -> create them, set the user_id later

        if should_be_present:
            # user should exist -> create them
            user_id = create_user(module, base_url, default_headers)
            result.update({
                'changed': True,
                'user_id': user_id,
                'exists': True,
                'created': True,
            })

            if not should_be_active:
                # for some reason the user should not be active after creation
                # -> deactivate them
                activate_user(module, base_url, default_headers, user_id, active=False)
                result.update({
                    'changed': True,
                    'exists': False,
                    'deactivated': True,
                })
        else:
            # user should not exist -> no need to do anything
            pass
    else:
        # the user is known at the external system -> set the user_id
        result.update({'user_id': user_id, 'exists': True})

        if should_be_present:
            # state is present
            if should_be_active:
                # user should be active
                if user_active:
                    # user exists and is already active -> no need to do anything
                    pass
                else:
                    # user exists and is not active, but should be -> activate them
                    activate_user(module, base_url, default_headers, user_id, active=True)
                    result.update({'changed': True, 'activated': True})
                    user_active = True
            else:
                # user should NOT be active
                if user_active:
                    # user exists and is active -> deactivate them
                    activate_user(module, base_url, default_headers, user_id, active=False)
                    result.update({
                        'changed': True,
                        'exists': False,
                        'deactivated': True,
                    })
                    user_active = False
                else:
                    # user exists and is already inactive -> no need to do anything
                    pass

            if user_active and should_update_user:
                # user exists and is active -> update the user
                update_user(module, base_url, default_headers, user_id)
                # can't really tell if the user actually changed, so always set changed to true
                result.update({'changed': True, 'updated': True})
        else:
            # state is absent -> delete them
            delete_user(module, base_url, default_headers, user_id)
            result.update({
                'changed': True,
                'exists': False,
                'deleted': True,
            })

    # we are done here
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
