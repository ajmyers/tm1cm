---
title: Promote a change with git
summary: Commit the model, change it, review the change, and put exactly that commit on the next server.
description: Use tm1cm and git to review a change to a TM1 model and promote exactly that change to another server.
order: 3
---
You keep the model in git, make a change, and put on the next server exactly the files that change touched, deleted ones included. Here the change is to PriceCube's rules, with an old view removed.

## Before you start

- **A project with the model in it:** [Set up a project and get your model](walkthroughs/first-project/). This one has two environments, `test` and `prod`. Here both point at the same SData sample; yours are different servers.

## Steps

1. **Commit the model as it is.** A project is an ordinary git repository:
   ::step promote init
   Nothing is left to commit: the log and `credentials.yaml` are in the scaffold's `.gitignore`.
   ::step promote status
2. **Make the change** and commit it. Edit the files, or change the model on `test` and `get` it again. Here a line is added to a rule, and a view is deleted:
   ::step promote change
3. **Review it.** The change is the files the commit touched, which is what a pull request shows a reviewer:
   ::step promote diff
4. **Put exactly that commit** on `prod`. Given files, tm1cm moves only their objects, whatever the filters in `tm1cm.yaml` say, and a file that's gone deletes its object:
   ::step promote put
   The rule is updated and the view deleted, and nothing else is touched.
5. **Put one file** the same way:
   ::step promote put-again

## Putting everything

`tm1cm --mode put --environment prod`, with no files, puts every object `tm1cm.yaml` includes: it compares the files with the server, and changes only what differs, deleting what the server has and the files don't. Run a `get` from that server into another folder first to see what it has, or use the [interactive shell](walkthroughs/interactive/) to look at the differences before doing them.

## What's next

[Run it from CI](walkthroughs/unattended/), so that a merged pull request is put on the server.
