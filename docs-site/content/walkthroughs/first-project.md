---
title: Set up a project and get your model
summary: Install tm1cm, make a project, connect it to your server, and write the model to files.
description: Set up tm1cm for an IBM Planning Analytics (TM1) server and get its model as files, step by step.
order: 1
---
You make a tm1cm project, tell it where your TM1 server is, and get its model: a file for each process, cube, rule, dimension, hierarchy and view. Each step shows what tm1cm printed when we ran it against IBM's SData sample.

## Before you start

- **A TM1 server, and a user on it.** Its REST API must be on: `HTTPPortNumber` in its `tm1s.cfg`. To follow along with IBM's SData sample, [run Planning Analytics on your own computer](/pa-docker/setup/): it answers at `http://localhost:8011`, and you log in as `admin` with the password `apple`.
- **git** on your computer. tm1cm needs Python too: [installing it with uv](#install) gets one for you.

## Install

::install

**Or in a virtual environment.**

::install-venv

## Steps

1. **Check tm1cm is installed** ([Install](#install), above): `tm1cm --help` lists its options.
2. **Make a project.** It's a folder; the name is yours. Here it's `sales`:
   ::step first-project scaffold
   ::step first-project cd
   It has a `config` folder: `default` holds what every environment shares, and `test` and `prod` are environments. Rename them, or add others, as your servers are: one folder per server.
   ::step first-project tree
3. **Say where the server is**, in its environment's `connect.yaml`. `base_url` is the server's address, without `/api/v1` (tm1cm adds that):
   ::step first-project connect
   A server with a certificate your computer doesn't trust needs `verify` too; [the connection settings](docs/settings/) have it, and the other ways to name a server.
4. **Say who logs in**, in `config/default/credentials.yaml`, for every environment, or in an environment's own folder:
   ::step first-project credentials
   SData's password is public, so it's in the file here. For your own server, leave it out, and tm1cm asks for it each time it connects, so it's never in a file. The scaffold's `.gitignore` keeps `credentials.yaml` out of git either way. A server in CAM security needs `namespace` too, or tm1cm lists the namespaces to pick from: [Log in to TM1](walkthroughs/logging-in/).
5. **Get the model.** tm1cm logs in, reads every object `tm1cm.yaml` includes, and writes it:
   ::step first-project get
6. **Look at what it wrote.** A folder for each type of object:
   ::step first-project folders
   and a file for each object, named after it:
   ::step first-project processes
   A process's file holds its settings, then each of its procedures, formatted the same way every time, so a change shows as just that:
   ::step first-project process

## What's next

Keep the project in git, and [promote a change](walkthroughs/promote/) from one server to another. To leave some objects out (control cubes, temporary processes, the elements another system maintains), change the filters in `config/default/tm1cm.yaml`: [every filter](docs/tm1cm-yaml/).
