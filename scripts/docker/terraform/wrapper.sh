#!/bin/bash

TF_BASE_VER="${TF_BASE_VER:-1.8}"

function get_azdo_access_token()
{
    # Try different methods of getting a Azure DevOps token.
    # Different devs have different habits
    if [ -n "${AZDO_PERSONAL_ACCESS_TOKEN}" ]; then
        echo "${AZDO_PERSONAL_ACCESS_TOKEN}"
        return
    fi

    if [ -f "${HOME}/.azdo_tok" ]; then
        cat ${HOME}/.azdo_tok
        return
    fi
}

function get_vault_token()
{
    # Try different methods of getting a Azure DevOps token.
    # Different devs have different habits
    if [ -n "${VAULT_TOKEN}" ]; then
        echo "${VAULT_TOKEN}"
        return
    fi

    if [ -f "${HOME}/.vault-token" ]; then
        cat ${HOME}/.vault-token
        return
    fi
}

function error()
{
    echo "${1}" >&2

    exit 1
}

SCRIPT_DIR="$(dirname "$(readlink -f "${0}")")"
DOCKERFILE="${SCRIPT_DIR}/Dockerfile"
DOCKER_LABEL="cli-terraform.core-tools"

echo "Wrapping docker for terraform around $(pwd)"

if [ ! -f "${DOCKERFILE}" ]; then
    error "Dockerfile not found: ${DOCKERFILE}"
fi

if ! which docker >&1 > /dev/null; then
    error "docker command is not available"
fi

CONTEXT_DIR="$(readlink -f "${SCRIPT_DIR}/../../..")"

TF_VER_PROCESSED="$(wget -q https://registry.hub.docker.com/v2/repositories/hashicorp/terraform/tags?name=$TF_BASE_VER -O - \
    | jq -r '.results[].name' \
    | sort -r \
    | grep -m 1 "^${TF_BASE_VER}.[0-9].*$")"

if ! docker build $@ \
    --build-arg "TF_VER=${TF_VER_PROCESSED}" \
    -t "${DOCKER_LABEL}" \
    -f "${DOCKERFILE}" \
    "${CONTEXT_DIR}"; then
    error "Docker build failed."
fi

STATE_DIR_ARG=""
if [ -d "${TF_LOCAL_STATE_DIR}" ]; then
  STATE_DIR_ARG="-v ${TF_LOCAL_STATE_DIR}:/state"
fi

docker run -it --rm \
    --network="host" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "${PWD}":/workspace \
    -e DISPLAY_HOSTNAME="${DOCKER_LABEL}" \
    -e PROMPT_BOX_COLOUR="\033[1;92m" \
    -e LS_COLORS="${LS_COLORS}" \
    -e TMUX="${TMUX}" \
    -e AUTH0_DOMAIN="${AUTH0_DOMAIN}" \
    -e AUTH0_CLIENT_ID="${AUTH0_CLIENT_ID}" \
    -e AUTH0_CLIENT_SECRET="${AUTH0_CLIENT_SECRET}" \
    -e GITLAB_TOKEN="${GITLAB_TOKEN}" \
    -e GITLAB_URI="${GITLAB_URI}" \
    -e GITLAB_BASE_URL="${GITLAB_BASE_URL}" \
    -e GITLAB_HOST="${GITLAB_HOST}" \
    -e GITLAB_API_HOST="${GITLAB_API_HOST}" \
    -e GITLAB_REPO="${GITLAB_REPO}" \
    -e GITLAB_GROUP="${GITLAB_GROUP}" \
    -e AZDO_ORG_SERVICE_URL="${AZDO_ORG_SERVICE_URL}" \
    -e AZDO_PERSONAL_ACCESS_TOKEN="$(get_azdo_access_token)" \
    -e AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}" \
    -e AWS_REGION="${AWS_REGION}" \
    -e AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}" \
    -e AWS_SESSION_TOKEN="${AWS_SESSION_TOKEN}" \
    -e VAULT_ADDR="${VAULT_ADDR}" \
    -e VAULT_TOKEN="$(get_vault_token)" \
    ${STATE_DIR_ARG} \
    -w /workspace \
    --entrypoint /bin/bash \
    "${DOCKER_LABEL}"
