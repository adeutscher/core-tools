This directory contains a Dockerfile for making an enclosed environment
    from which to run a specific version of Terraform.

Run `wrapper.sh` from a root directory that holds every Terraform project and
    every module they reference, then `cd` to a project inside the container.
    Only the current directory is mounted, so relative module paths that leave a
    single project directory would not resolve if started from there.

Credentials are passed through from the calling shell:

* `GITLAB_TOKEN`, or the contents of `~/.gitlab_tok`
* `VAULT_TOKEN`, or the contents of `~/.vault-token`
* `AZDO_PERSONAL_ACCESS_TOKEN`, or the contents of `~/.azdo_tok`
* Every `TF_VAR_*` variable, by name
* The SSH agent (`SSH_AUTH_SOCK`) and `~/.ssh/known_hosts`, for git over SSH

The image includes the GitLab CLI (`glab`). Set `GITLAB_HOST` for a self-managed
    instance.

Arguments used with terraform-wrapper are passed directly to `docker build`.
