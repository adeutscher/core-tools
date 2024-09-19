#!/bin/bash

function get_azdo_access_token()
{
    # Try different methods of getting a Azure DevOps token.
    # Different devs have different habits
    if [ -n "${AZDO_PERSONAL_ACCESS_TOKEN}" ]; then
        echo "${AZDO_PERSONAL_ACCESS_TOKEN}"
        return
    fi

    if [ -f "~/.azdo_tok" ]; then
        cat ~/.azdo_tok
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
DOCKER_LABEL="cli-rockylinux.core-tools"

echo "Wrapping docker around $(pwd)"

if [ ! -f "${DOCKERFILE}" ]; then
    error "Dockerfile not found: ${DOCKERFILE}"
fi

if ! which docker >&1 > /dev/null; then
    error "docker command is not available"
fi

CONTEXT_DIR="$(readlink -f "${SCRIPT_DIR}/../../..")"

if ! docker build $@ \
    --build-arg "HOST_USER=$(whoami)" \
    --build-arg "HOST_USER_ID=${UID}" \
    -t "${DOCKER_LABEL}" \
    -f "${DOCKERFILE}" \
    "${CONTEXT_DIR}"; then
    error "Docker build failed."
fi

docker run -it --rm \
    --network="host" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "${PWD}":/workspace \
    -e DISPLAY_HOSTNAME="${DOCKER_LABEL}" \
    -e PROMPT_BOX_COLOUR="\033[1;92m" \
    -e LS_COLORS="${LS_COLORS}" \
    -e TMUX="${TMUX}" \
    -e GITLAB_TOKEN="${GITLAB_TOKEN}" \
    -e GITLAB_URI="${GITLAB_URI}" \
    -e GITLAB_HOST="${GITLAB_HOST}" \
    -e GITLAB_API_HOST="${GITLAB_API_HOST}" \
    -e GITLAB_REPO="${GITLAB_REPO}" \
    -e GITLAB_GROUP="${GITLAB_GROUP}" \
    -e AZDO_ORG_SERVICE_URL="${AZDO_ORG_SERVICE_URL}" \
    -e AZDO_PERSONAL_ACCESS_TOKEN="$(get_azdo_access_token)" \
    -e AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}" \
    -e AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}" \
    -e AWS_SESSION_TOKEN="${AWS_SESSION_TOKEN}" \
    -w /workspace \
    --entrypoint /bin/bash \
    "${DOCKER_LABEL}"
