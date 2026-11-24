---
kicker: IBM Planning Analytics · Python
tagline: Your TM1 model in files, so you can review, version and promote it with git
description: tm1cm moves IBM Planning Analytics (TM1) models between servers and files: processes, cubes, rules, dimensions, views, subsets, chores and applications, one file each, ready for git.
card: A command-line tool that moves TM1 objects between environments and your file system, so a TM1 application can live in source control, and a change can be reviewed and promoted with git. Written in Python.
---
tm1cm copies a TM1 model to files, one per object, and back: processes, cubes and their rules, dimensions and hierarchies, views, subsets, chores and applications. Keep them in git, review a change before it goes live, and put exactly what was reviewed on the next server.

## Quick start

1. **Install it.**
   ::install
2. **Make a project.** A folder with a config for each environment.
   ::step first-project scaffold
3. **Say where your server is**, in the environment's `connect.yaml`:
   ::step first-project connect
   and who logs in, in `credentials.yaml`:
   ::step first-project credentials
   SData's password is public, so it's in the file here. For your own server, leave it out: tm1cm asks for it each time it connects.
4. **Get the model.** Every object becomes a file under `data/`.
   ::step first-project get
5. **Put it on another server** with `tm1cm --mode put --environment prod`, or only the files a commit changed: [Promote a change with git](walkthroughs/promote/).

## Walkthroughs

Step by step, with what tm1cm printed when we ran each step against IBM's SData sample:

::walkthroughs

## Build it with an agent

Hand this prompt to a coding agent to set up tm1cm for your servers. It names how to install it, the docs and the walkthroughs, and asks you for anything it can't work out.

::prompt

## What it does

- **Get and put:** `get` writes the server's model to files, and `put` writes the files to a server. Only what differs is changed, in the order TM1 needs: dimensions before the cubes made of them, a process before the chores that run it.
- **Only what you choose:** filters in `tm1cm.yaml` pick the objects, by name and with wildcards: every process but the temporary ones, the hierarchies' elements but not the ones another system maintains. [The filters](docs/tm1cm-yaml/).
- **Exactly a commit:** give `put` the files a commit changed, deleted ones included, and it puts that change and nothing else.
- **Pick by hand:** the interactive shell lists what differs between two environments, and does what you pick.
- **Every way TM1 logs in:** TM1's own security, CAM with a password, and CAM namespaces that sign in through a browser (OpenID Connect, SAML), worked out from the server. A password is asked for rather than kept in a file. [Logging in](walkthroughs/logging-in/).
- **Made for automation:** exit codes that say what went wrong, and a report in the log to attach to an issue. [Running unattended](walkthroughs/unattended/).
