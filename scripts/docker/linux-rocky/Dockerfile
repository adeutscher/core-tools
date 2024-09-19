FROM rockylinux:9.1
RUN dnf upgrade -y

# **************************************************************
# Install packages
# **************************************************************
RUN dnf install -y \
  git \
  iputils \
  net-tools \
  procps-ng \
  python \
  tmux \
  unzip \
  wget

# **************************************************************
# Install TAC cert
# **************************************************************  

WORKDIR /etc/pki/ca-trust/source/anchors/
COPY files/pki/ca-certificates/tac-ca.crt .
RUN update-ca-trust force-enable

# **************************************************************
# Set user to match host invoker
# **************************************************************  
ARG HOST_USER
ARG HOST_USER_ID
RUN useradd -m -u ${HOST_USER_ID} ${HOST_USER}
#RUN mkdir "/home/${HOST_USER}"
RUN ls -Rl "/home/"
RUN chown "${HOST_USER}" "/home/${HOST_USER}"
RUN whoami
USER ${HOST_USER}

# **************************************************************
# Install prompt customizations
# **************************************************************  
RUN git clone https://github.com/adeutscher/core-tools ~/tools/core-tools
RUN ~/tools/core-tools/scripts/setup/setup-tools.sh
RUN echo 'alias ls="ls --color=auto"' >> ~/.bashrc

RUN git config --global user.name "Alan Deutscher"
RUN git config --global user.email "adeutscher@gmail.com"

WORKDIR /workspace
