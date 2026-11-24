---
title: Pick changes in the interactive shell
summary: See what differs between two environments, and do only the changes you pick.
description: tm1cm's interactive shell: compare two TM1 environments or a project and a server, stage changes and do them.
order: 4
---
The interactive shell compares two places (a server and the project's files, or two servers) and lists what would change, so you can pick what to do. Here the project has a change to PriceCube's rules that `prod` doesn't have yet.

## Steps

1. **Start the shell** in the project's folder with `tm1cm`, and type `ls apps` at its prompt. It lists the places you can compare: the project's files (`local`) and each environment. `exit`, `quit` or Ctrl-D leaves the shell:
   ::step interactive apps
2. **Compare two of them** with `migrate <from> <to>`, and `ls` to see what would change on the second: here the change to PriceCube's rules is the only difference. Pick what to do with `add` (wildcards work: `add UPDATE_PROCESS:*`), check it with `ls stage`, and do it with `do`, which asks first:
   ::step interactive migrate
   `rm` takes an operation back off the stage, and `do all` does every one.

## A backup first

The shell can run a TI process before `do`, to back the server up: `backup_process` in [tm1cm.yaml](docs/tm1cm-yaml/#backup-before-migrating), with `backup_on_migrate` to run it by default, and `backup_allow_override` to be asked each time.

## What's next

[Run tm1cm unattended](walkthroughs/unattended/), for the changes that don't need a person to pick them.
