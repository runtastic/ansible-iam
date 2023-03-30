# Identity Access Management with Ansible

This repository contains roles and playbooks to use Ansible for Identity Access
Management.

We recommend using **Ansible Automation Controller / Ansible Tower** or
[AWX](https://github.com/ansible/awx) to get the most out of this solution.

Currently implemented:

- [AWS](https://aws.amazon.com/)
- [Azure](https://portal.azure.com/)
- [Contentful](https://www.contentful.com/)
- [GitHub](https://github.com/)
- [Google Workspace](https://workspace.google.com/)
- [Miro](https://miro.com)
- [Slack](https://slack.com)

## Examples

Performing a local run of roles.

### AWS

```bash
# aws_manage_users.yml
ansible-playbook -i localhost, -c local ./aws_manage_users.yml -e @./example_vars/aws.json \
-e "aws_api_url=https://scim.eu-central-1.amazonaws.com/<ID>/scim/v2/ aws_api_token=<AWS_API_TOKEN>"

# aws_manage_groups.yml
ansible-playbook -i localhost, -c local ./aws_manage_groups.yml -e @./example_vars/aws.json \
-e "aws_api_url=https://scim.eu-central-1.amazonaws.com/<ID>/scim/v2/ aws_api_token=<AWS_API_TOKEN>"
```

### Azure

```bash
# azure_manage_users.yml
ansible-playbook -i localhost, -c local ./azure_manage_users.yml -e @./example_vars/azure.json \
-e "azure_client_id=<AZURE_CLIENT_ID> azure_client_secret=<AZURE_CLIENT_SECRET> azure_tenant_id=<AZURE_TENANT_ID>"

# azure_manage_groups.yml
ansible-playbook -i localhost, -c local ./azure_manage_groups.yml -e @./example_vars/azure.json \
-e "azure_client_id=<AZURE_CLIENT_ID> azure_client_secret=<AZURE_CLIENT_SECRET> azure_tenant_id=<AZURE_TENANT_ID>"
```

### Contentful

```bash
# contentful_manage_users.yml
ansible-playbook -i localhost, -c local ./contentful_manage_users.yml -e @./contentful-example.json \
-e "contentful_base_url=https://api.contentful.com contentful_access_token=<CONTENTFUL_ACCESS_TOKEN> contentful_org_id=<CONTENTFUL_ORG_ID>"
```

### GitHub

```bash
# github_manage_users.yml
ansible-playbook -i localhost, -c local ./github_manage_users.yml -e @./example_vars/github.json \
-e "github_api_url=https://api.github.com github_api_org=<GITHUB_ORG> github_api_token=<GITHUB_API_TOKEN>"
```

### Google Workspace

```bash
# google_manage_users.yml
ansible-playbook -i localhost, -c local ./google_manage_users.yml -e @./example_vars/google.json \
-e "google_subject=automation@guardians.com google_private_key=<GOOGLE_API_PRIVATE_KEY>"

# google_manage_groups.yml
ansible-playbook -i localhost, -c local ./google_manage_groups.yml -e @./example_vars/google.json \
-e "google_subject=automation@guardians.com google_private_key=<GOOGLE_API_PRIVATE_KEY>"
```

### Miro

```bash
# miro_manage_users.yml
ansible-playbook -i localhost, -c local ./miro_manage_users.yml -e @./example_vars/miro.json \
-e "miro_api_token=<MIRO_API_TOKEN>"
```

### Slack

```bash
# slack_manage_users.yml
ansible-playbook -i localhost, -c local ./slack_manage_users.yml -e @./example_vars/slack.json \
-e "slack_api_token=<SLACK_API_TOKEN>"
```
