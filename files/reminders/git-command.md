# Create Bare Reponsitory

To create a new 'bare' repo meant only for cloning from:

    git init --bare [directory]

# Remote Access to Clones

`git` being `git`, it is possible to host a repository in any location
    that you can access over SSH. You can even clone from another clone
    on another machine.

However, by default you may not push up to the clone. Because the clone
    is a non-bare repository, access must be allowed:

* From the root of the remote clone that you wish to be able to push to,
    open `.git/config` for editing.
* Under the `[receive]` header, add `denyCurrentBranch = warn`.
   You may alternately specify 'ignore' instead of 'warm'

Pushing to a non-bare repo makes the checked out version on the server look a bit strange.
In order to get the latest version (assuming that your current directory contains all changed files):
```bash
git reset HEAD
git checkout .
```

# Squashing Branches

Front-end services such as GitLab or GitHub offer the option to
  conveniently squash branches that are the subjects of pull requests.
  This has a few benefits, such as:

* Prevents trial-and-error, end-of-session-checkpoint, or immediate-hindsight commits
    from cluttering the main branch.
* Could potentially keep sensitive data information that was accidentally committed
    to a development branch out of the main branch's history.
* In tools such as GitLab, GitHub, or similar, this allows the main branch to be locked down
    in order for enforce code review or continuous integration via pull requests.
    This is especially useful for multi-user projects, but could be set up
    for single-user projects as well.

As handy as these services are, squashing branches seems like a useful thing to note how
  to do manually. After learning how to do this, the technique was much simpler than I thought.
  However, like other reminders I'm still documenting it here in case I forget in the future.

For example, say we had the following situation:

* Our demo project is forked from the 'master' branch into a
  'dev' branch at a specific commit.
* The 'dev' branch has 2 or more commits in it.
* Per the topic, we would like the merging of 'dev' into 'master' to appear
  in 'master' as a single commit.

To do this from the command line:

1. Checkout the branch that you want to merge **into**.
2. Use the `merge` sub-command with the `--squash` fix. Assuming that there
  are no conflicts, this should resolve any changes (resolving conflicts
  is not the focus of this section).
3. Commit your changes. Note that the initial commit message will include all
  of the commit messages from the source branch, so be sure to trim this down
  if you want to only leave a short summary.
4. Observe in the git log for the destination branch that only a single new
  commit entry has been created.

Example:

    git checkout master
    git merge --squash dev-branch
    git commit
