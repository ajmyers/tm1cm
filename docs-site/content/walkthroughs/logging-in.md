---
title: Log in to TM1
summary: Keep passwords out of files, sign in to CAM and through a browser, and give settings on the command line.
description: How tm1cm logs in to IBM Planning Analytics (TM1): TM1 security, CAM namespaces, browser sign-in (OpenID Connect, SAML) and CAM passports.
order: 2
---
tm1cm logs in the way your server wants, and asks for what it needs rather than keeping it in a file. You see what happens without a password, and how to give one for a single run.

## How tm1cm works out the login

- **TM1's own security:** a user and a password. With no password in `credentials.yaml`, tm1cm asks for it when it connects, and again when TM1 refuses it, up to three times. A user whose password is empty is logged in without being asked.
- **CAM with a password** (LDAP, Active Directory): the same, with `namespace` set. Without one, tm1cm asks Cognos for its namespaces and lets you pick.
- **CAM through a browser** (OpenID Connect through Entra ID, Okta, Keycloak and the like, or SAML): set `namespace`, and tm1cm opens your namespace's own login in a browser window (Chrome, Edge, Brave or Chromium, with a profile of its own), and logs in with the passport Cognos gives it. While your provider remembers you, no window is needed.
- **A CAM passport** you already have: `cam_passport` with `base_url` is all it needs. A passport expires.
- **Windows single sign-on** through a CAM gateway: `gateway`.

Every setting is in [the connection settings](docs/settings/), and `auth` says which way to log in when tm1cm shouldn't work it out.

## Steps

1. **Leave the password out** of `credentials.yaml`:
   ::step logging-in credentials
2. **Run tm1cm.** In a terminal it asks for the password. Here it has no terminal to ask in (as in a scheduled job), so it tries the empty password, and TM1 refuses it. The message says what to check, and the exit code is 4:
   ::step logging-in no-terminal
3. **Give a setting for one run** with `--connect KEY=VALUE` (or `-c`), once for each. It wins over `connect.yaml` and `credentials.yaml`, for any setting:
   ::step logging-in connect-option
   A password given this way can end up in your shell's history: in a terminal, leave it out and type it when asked.

## Signing in through the browser

- A hidden window is tried first. When your provider needs you, a window opens, and tm1cm says so.
- Without a terminal, or on Linux without a display, only the hidden window is tried, and if that isn't enough the message says what to set instead.
- If the browser can't sign you in, tm1cm offers a user and password (for a namespace that takes one), pasting a CAM passport, trying again, or cancelling.
- The browser's profile is tm1cm's own, in your user cache folder, never your own browser's.

## What's next

[Run tm1cm unattended](walkthroughs/unattended/), where there's nobody to ask, or [promote a change with git](walkthroughs/promote/).
