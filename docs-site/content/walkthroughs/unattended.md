---
title: Run tm1cm unattended
summary: Exit codes and logs for CI and scheduled jobs, with nobody there to answer.
description: Run tm1cm from CI or a scheduler: exit codes, the log, and logging in without a person to ask.
order: 5
---
In CI or a scheduled job there's nobody to type a password or sign in. tm1cm asks nothing there, and its exit code and log say what happened.

## Logging in without a person

- tm1cm only asks when it runs in a terminal. Elsewhere, a password that isn't set is sent empty, and anything else it needs ends the run with a message naming the setting.
- Give the password from your CI's secrets with `--connect password=...` (`-c`), so it's never in a file: every setting can be given this way. Or set `cam_passport` for a CAM server.
- A browser sign-in can't happen without a person: use a namespace that takes a password, or a passport.

## Steps

1. **A run that works** exits with 0:
   ::step unattended ok
2. **A server that isn't there** exits with 3:
   ::step unattended unreachable
   and the end of the output says what went wrong, and what to check:
   ::step unattended unreachable-log
3. **A login TM1 refuses** exits with 4:
   ::step unattended refused
   ::step unattended refused-log

## Exit codes

A script or CI job can tell what went wrong from the exit code: 2 for a setting, file or argument, 3 when TM1 can't be reached, 4 when the login is refused, 5 when TM1 refused some objects (the rest were done, and the failures are listed at the end), and 70 for something unexpected. [Every exit code](docs/exit-codes/).

## The log

Every run writes `<project>.log` in the folder it runs in (`--log` names another): what it did, and when something goes wrong, a full report with the traceback, the versions and the servers. Passwords and passports are masked in it. Attach it when you [report an issue](https://github.com/ajmyers/tm1cm/issues). `--debug` adds every request tm1cm sends.
