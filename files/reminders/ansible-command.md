
# Ansible

This file is dedicated to `ansible` and `ansible-playbook`.

Other useful references:

* [Main Ansible Documentation Index](http://docs.ansible.com/ansible/latest/index.html)
* [Ansible Module Index](http://docs.ansible.com/ansible/latest/modules/modules_by_category.html)

## Inventories

Ansible inventory files are ini-format listings of hosts.

Example:

    [vms]
    192.168.0.10
    192.168.0.11
    192.168.0.12

    [servers]
    server-a

Names can be IP addresses, domain names, and/or SSH aliases as per `~/.ssh/config`.

To create an inventory in the command line without creating a dedicated inventory file:

    ansible -i 192.168.0.10,192.168.0.11 all ...

The addition of a comma in the argument is what tells `ansible` to accept an ad-hoc list rather than to look for an inventory file.

After defining an inventory, you must specify a pattern to match by. Patterns can be:

* ***all*** for every host in inventory.
* Section names.
* Exact matches to a host.
* Wildcards are also accepted (e.g. 192.168.0.\*

## Playbooks

Playbooks are used to orchestrate events in a scripted order.

Playbooks are in YAML format. This is an example document:

    ---

    # Set up a Fedora Workstation.
    # My first major effort with Ansible playbooks.

    - hosts: "{{ variable_host | default('fedora-workstations') }}"
      # Example to override 'fedora-workstations' grouping: --extra-vars "variable_host=127.0.0.1"

      environment:
        ANSIBLE: 1

      tasks:
      - name: Install Fedora Packages
        when: (ansible_distribution == "Fedora")
        block:
          # Restrict to Fedora systems for the time being.
          # Support for other RedHat-based distributions can be added pending testing.

          # Fail if we cannot confirm DNF as our main package manager.
          - name: "Confirm DNF System"
            fail: msg="DNF not our primary package manager."
            when: not (ansible_pkg_mgr == "dnf")

          ## Development Tools and CLI items

          - name: install other development tools and cli items
            dnf: name={{item}} state=latest
            with_items:
              - vim      # vim editor
              - tmux     # tmux multiplexer
              - svn      # Subversion version control
              - git      # Git version control
              - astyle   # Artistic Style code formatter

          - name: install the 'development-tools' package group
            dnf: name='@development-tools' state=latest
            become: yes
            # Install failed when run against a Fedora 25 machine due to a module problem.
            # F25 is already EoL at time of writing anyways (2018-05-01, Ansible 2.4.1), so this is not a major concern.
            # Tested on:
            #   F25->F27 (Success)
            #   F25->F25 (FAIL)
            #   F26->F25 (FAIL)
            #   F26->F26 (Success)
            # Possibly related to https://github.com/ansible/ansible/issues/26868.
            when: (ansible_distribution == "Fedora" and ansible_distribution_version >= "26")

Notes on the above:

* YAML is a bit sensitive about tab indents, similar to Python code.
* Even when a value is a number, it must still be enclosed in quotes. Ansible's comparison operators will handle things.
* The ***when*** clause is useful for confirming that a task is valid for a particular system.
* Comments begin with ***#***.
* Items in the ***environment*** section are set as environment variables that we can use.

### Facts

By default, the first step of an `ansible` playbook is to gather information from each target system, termed as "facts". These can be used as variables in later checks.

The `setup` module can be used to output example facts on a particular system.

    ansible -m setup ...

Below is a heavily redacted example output to demonstrate accessing facts:

    localhost | SUCCESS => {
        "ansible_facts": {
            "ansible_all_ipv4_addresses": [ "192.168.0.1", "192.168.1.1" ],
            "ansible_date_time": {
                "date": "2018-05-01", 
                "day": "01", 
                "epoch": "1525230087", 
                "hour": "20", 
                "iso8601": "2018-05-02T03:01:27Z", 
                "iso8601_basic": "20180501T200127585897", 
                "iso8601_basic_short": "20180501T200127", 
                "iso8601_micro": "2018-05-02T03:01:27.585986Z", 
                "minute": "01", 
                "month": "05", 
                "second": "27", 
                "time": "20:01:27", 
                "tz": "PDT", 
                "tz_offset": "-0700", 
                "weekday": "Tuesday", 
                "weekday_number": "2", 
                "weeknumber": "18", 
                "year": "2018"
            },
        },
        "changed": false, 
        "failed": false
    }

Examples of accessing variables:

* To use the day of the week: `ansible_date_time.weekday` (Tuesday).
* To use the first IP in `ansible_all_ipv4_addresses`: `ansible_all_ipv4_addresses.0`

### Other Major Playbook Clauses

Other important headers in a playbook:

* ***hosts***: Defines target range. If you need to only run against a subset of this list, use the `-l` switch with `ansible-playbook`.
* ***when***: Used to restrict when a task or block is run.
* ***become***: Announce that the host needs to elevate its permissions. Can be applied to an entire playbook or specific tasks. Equivalent to invoking `-b` switch.
* ***environment***: Set environment variables in host sessions.

## Module Examples

Examples of specific modules being used. Examples do not include matching specifications to cut down on clutter.

### Ping

A ping is a basic check-in.

   ... -m ping

### Shell Command

To run a command on each of the host systems.

   ... -m shell -a "echo 'example command'"

If you are running this in a playbook and want to get command output you must use the ***debug*** option:

    - name: env task
      shell: "env"
      register: env_output

    - debug: var=env_output.stdout_lines

Below is an example of taking command output and using it as a condition in a later task:

    - name: check dnf version
      shell: warn=false dnf --version | head -n1
      register: dnf_check
      changed_when: false # Never announce as changed.

    # Tidy Up
    - name: Autoremove unneeded packages installed as dependencies
      dnf: autoremove=yes
      become: yes
      # Requires DNF v2.0.1 or greater.
      when: dnf_check.stdout is version('2.0.1', '>=')

The above example on storing output also demonstrates:

* Comparing version values
* Mixing a "free form" command with other arguments. The static argument "warn" should be placed in front of the rest of the command.

Other notes:

* [Shell Module: Ansible Documentation](http://docs.ansible.com/ansible/latest/modules/shell_module.html)

### DNF

To install a package with `dnf`:

    ansible -m dnf -a "name=astyle"

In a playbook, the following can be done to install packages en mass without repeating all of the syntax:

    - name: install other development tools and cli items
      dnf: name={{item}} state=latest
      with_items:
        - vim      # vim editor
        - tmux     # tmux multiplexer
        - svn      # Subversion version control
        - git      # Git version control
        - astyle   # Artistic Style code formatter

Notes:

* `yum` accepts similar basic syntax ([Manual Link](http://docs.ansible.com/ansible/latest/modules/yum_module.html)).
* [DNF Module: Ansible Documentation](http://docs.ansible.com/ansible/latest/modules/dnf_module.html)

## Other Tasks

### Password Authentication

By default, ansible will not attempt to connect with a password by default. The `-k` switch is required to create a prompt that will collect the password to be used if it is required. `ansible` will then use this password to connect to all hosts for which key pair authentication does not work. The password is expected to be the same for all hosts that require the password to be input, but if a host with a valid key pair has a different password than no error will occur. If there is a host for which the password would be different, then that will require a second `ansible` run. 

Example:

    ansible -i 10.20.30.40, -m ping all -k

### Privilege Escalation

Some operations may need to be done as a different user than the initial remote user (e.g. becoming root to install packages). To do this, the encouraged method is to use the `-b` switch (standing for "become").

Short of some cloud systems and Raspberry Pis, many distributions will require a password in order to elevate a user. Similar to password authentication for signing into machines without a key pair, no password is used by default. The `-K` switch is used to provide an escalation password. If a password was also used with `-k`, then empty input at the escalation prompt will default to using the sign-in password. 

    ansible -i "server," -m shell -a whoami -bK

If you need to become a specific user other than root, use the `--become-user user` switch for `ansible`, and `become_user` within a playbook.

### File Management

#### Create Directory

To create a directory in a playbook:

    - name: create directory
      file: path="/path/to/directory" state=directory mode=0755

For more information on arguments, see the page [File Module: Ansible Documentation](https://docs.ansible.com/ansible/2.5/modules/file_module.html) page.

#### Create Symbolic Link

To create a symbolic link in a playbook:

    - file:
        state: link            # Specify that we are making a symbolic link
        src: /file/to/link/to  # Target of symbolic link 
        dest: /path/to/symlink # Location of symbolic link
        owner: foo
        group: foo

The comments should help confirm the phrasing of which end of the symbolic link is which. For more information on arguments, see the page [File Module: Ansible Documentation](https://docs.ansible.com/ansible/2.5/modules/file_module.html) page.

#### Transfer File(s) to Remote

To transfer a file:

    - name: Copy a file
      copy: src="/home/user/source" dest="/home/user/remote-copy"

Relative paths are also accepted. In playbooks, they will be relative to your playbook's directory. Consider the following silly example to copy the playbook (assumed to be named `copy-demo.yml`):

    ---
    - hosts: localhost

      vars:
        playbook_name: copy-demo.yml # Relative path to copy demo.
        directory_name: "{{ ansible_user_dir }}/ansible-demo" # Directory to place copy in.

      tasks:
      - name: create directory
        file: path="{{ directory_name }}" state=directory

      - name: copy playbook
        copy: src="{{ playbook_name }}" dest="{{ directory_name }}"


Directories can also be transferred, in a style that Ansible's documentation likens to `rsync`. If the source path ends with '/', then the contents within the directory will be copied. If the source path does not end with '/', then the entire directory will be copied.

For more information, see [Ansible Documentation: Copy Module](http://docs.ansible.com/ansible/latest/modules/copy_module.html)

### Scripts

Some examples of running a script taken from the Ansible documentation page for the [Script Module](http://docs.ansible.com/ansible/latest/modules/script_module.html):

    # Example from Ansible Playbooks
    - script: /some/local/script.sh --some-arguments 1234

    # Run a script that creates a file, but only if the file is not yet created
    - script: /some/local/create_file.sh --some-arguments 1234
      args:
        creates: /the/created/file.txt

    # Run a script that removes a file, but only if the file is not yet removed
    - script: /some/local/remove_file.sh --some-arguments 1234
      args:
        removes: /the/removed/file.txt

Notes:

* The `creates` option can be used to skip a script when a file that is expected to create already exists.
* The `removes` option can be used to skip a script when a file that is expected to delete already does not exist.

### Lists

`ansible` is quite flexible when it comes to lists. Below is an example from the main Ansible Documentation pages that uses lists in many different ways ([Source](https://docs.ansible.com/ansible/2.5/plugins/lookup/items.html)):

    - name: "loop through list"
      debug:
        msg: "An item: {{item}}"
      with_items:
        - 1
        - 2
        - 3

    - name: add several users
      user:
        name: "{{ item }}"
        groups: "wheel"
        state: present
      with_items:
         - testuser1
         - testuser2

    - name: "loop through list from a variable"
      debug: msg="An item: {{item}}"
      with_items: "{{ somelist }}"

    - name: more complex items to add several users
      user:
        name: "{{ item.name }}"
        uid: "{{ item.uid }}"
        groups: "{{ item.groups }}"
        state: present
      with_items:
         - { name: testuser1, uid: 1002, groups: "wheel, staff" }
         - { name: testuser2, uid: 1003, groups: staff }
