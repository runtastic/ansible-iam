# Identity Access Management with Ansible

This repository contains roles and playbooks to use Ansible for Identity Access Management. 

We recommend using **Ansible Automation Controller / Ansible Tower** or [AWX](https://github.com/ansible/awx) to get the most out of this solution. 

Currently implemented:
- AWS
- GitHub
- Google Workspace

## Examples

Performing a local run of roles:

```bash
#### AWS ####

# aws_manage_users.yml
ansible-playbook -i localhost, -c local ./aws_manage_users.yml -e @./aws-example.json \
-e "aws_api_url=https://scim.eu-central-1.amazonaws.com/<ID>/scim/v2/ aws_api_token=<AWS_API_TOKEN>"

# aws_manage_groups.yml
ansible-playbook -i localhost, -c local ./aws_manage_groups.yml -e @./aws-example.json \
-e "aws_api_url=https://scim.eu-central-1.amazonaws.com/<ID>/scim/v2/ aws_api_token=<AWS_API_TOKEN>"

#### GitHub ####

# github_manage_users.yml
ansible-playbook -i localhost, -c local ./github_manage_users.yml -e @./github-example.json \
-e "github_api_url=https://api.github.com github_api_org=<GITHUB_ORG> github_api_token=<GITHUB_API_TOKEN>"

#### Google Workspace ####

# google_manage_users.yml
ansible-playbook -i localhost, -c local ./google_manage_users.yml -e @./google-example.json \
-e "google_subject=automation@guardians.com google_private_key=<GOOGLE_API_PRIVATE_KEY>"

# google_manage_groups.yml
ansible-playbook -i localhost, -c local ./google_manage_groups.yml -e @./google-example.json \
-e "google_subject=automation@guardians.com google_private_key=<GOOGLE_API_PRIVATE_KEY>"
```