
# AWS

Reminders for Amazon Web Services CLI utility.

## Installation and Setup

To install for your local user:

    pip install --local --upgrade awscli

To get automated prompts for configuring credentials:

    aws configure

## S3

To copy a file:

    aws s3 cp test-file s3://my-bucket/test-file

To sync a directory:

    aws s3 sync dir/ s3://my-bucket/backup-dir/
