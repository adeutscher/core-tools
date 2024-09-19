FROM rockylinux:9.1

# **************************************************************
# Install packages
# **************************************************************
RUN dnf upgrade -y \
  && dnf clean all \
  && dnf install -y \
  dnf-plugins-core \
  git \
  iputils \
  jq \
  net-tools \
  procps-ng \
  python \
  python-pip \
  tmux \
  unzip \
  yum-utils

RUN git config --global user.name "Alan Deutscher" && git config --global user.email "adeutscher@gmail.com"

# **************************************************************
# Install prompt customizations
# **************************************************************
RUN git clone https://github.com/adeutscher/core-tools /root/tools/core-tools && /root/tools/core-tools/scripts/setup/setup-tools.sh

# **************************************************************
# Install Terraform
# **************************************************************
ARG TF_VER
RUN curl -s "https://releases.hashicorp.com/terraform/${TF_VER}/terraform_${TF_VER}_linux_amd64.zip" > tf.zip && unzip tf.zip && mv terraform /usr/local/bin/

# **************************************************************
# Install Vault
# **************************************************************

RUN dnf config-manager --add-repo https://rpm.releases.hashicorp.com/RHEL/hashicorp.repo && dnf install -y vault

# **************************************************************
# Install Docker CLI
# **************************************************************

RUN dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo && dnf install -y docker-ce-cli

# **************************************************************
# Install TFLint
# **************************************************************
RUN curl -s https://raw.githubusercontent.com/terraform-linters/tflint/master/install_linux.sh | bash

# **************************************************************
# Install tflocal
# **************************************************************

RUN pip install terraform-local

# **************************************************************
# Install TAC Certificate Authority
# **************************************************************

WORKDIR /etc/pki/ca-trust/source/anchors/
COPY files/pki/ca-certificates/tac-ca.crt .
RUN update-ca-trust force-enable

# **************************************************************
# Install AWSCLIv2
# **************************************************************
WORKDIR /build
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
RUN unzip awscliv2.zip
RUN ./aws/install

RUN echo 'alias ls="ls --color=auto"' >> ~/.bashrc
RUN echo 'tflint --init' >> ~/.bashrc
RUN echo 'terraform init --upgrade' >> ~/.bashrc
RUN echo 'terraform plan' >> ~/.bash_history

RUN rm -rf /build

WORKDIR /workspace
