
# Squashing Branches

Front-end conveniences such as GitLab or GitHub offer the option to
  conveniently squash branches that are the subjects of pull requests
  so that development trial-and-error commits don't clutter up the
  commit log of a project's main branch (and possibly to keep sensitive
  data accidentally commited to a development branch don't end up in the
  history of the min branch).

As handy as these services are, it seems like a useful thing to note how
  to do manually in case it ever comes up. After learning how to do this,
  the technique was much simpler than I thought. However, like other
  reminders I'm still documenting it here in case I forget in the future.

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
