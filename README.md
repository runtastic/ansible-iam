# Identity Access Management with Ansible

This repository contains roles and playbooks to use Ansible for Identity Access Management. 

We recommend using **Ansible Automation Controller / Ansible Tower** or [AWX](https://github.com/ansible/awx) to get the most out of this solution. 

Currently implemented:
- AWS
- GitHub

## Examples

Performing a local run of the github_manage_users role:

```bash
ansible-playbook -i localhost, -c local ./github_manage_users.yml -e @./github-example.json -e "github_api_url=https://api.github.com github_api_org=<GITHUB_ORG> github_api_token=<GITHUB_API_TOKEN>"
```
