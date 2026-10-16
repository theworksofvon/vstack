---
name: auth0
description: Change Costmine's Auth0 staging tenant with the auth0 CLI. Use when the user mentions Auth0, an API's permissions or scopes, a client grant, or what an M2M app's token may do.
---

Read and change Costmine's Auth0 **staging** tenant, `costmine-stage.us.auth0.com`,
with the `auth0` CLI. Production is out of reach on purpose: the CLI is logged
in to staging only, and the dotfiles guard (below) blocks writes anywhere else.

Assumes the `auth0` CLI is installed and logged in, and the dotfiles hooks are
active. Staging fronts `https://stage-auth.costmine.com`; its gateway API is
`https://stage-api.costmine.com/`.

## The guard

`$HOME/.dotfiles/agents/hooks/rules.json` decides every `auth0` command before
it runs. Reads pass on any tenant, creates and updates pass on staging only,
deletes never pass, and login, logout and tenant switching are the user's.
Read that file for the exact lists rather than guessing.

When the guard blocks a command, it is working. Hand the user the exact
command to run themselves with `!`, or propose the rule to move between the
`allow` and `block` lists. `rules.json` is locked against agents; to have you
make the edit, the user runs `rules-lock off`, and you change only what they
agreed to.

## Every change

1. **Confirm the tenant.** `auth0 tenants list --json` shows
   `costmine-stage.us.auth0.com` as active. Anything else: stop, and tell the
   user to log in to staging themselves.
2. **Read the current state** and keep it as the _before_ snapshot:
   - API permissions: `auth0 apis show <audience> --json`, the `scopes` array.
   - Client grants: `auth0 client-grants list --audience <audience> --json`,
     each grant's `client_id` and `scope`. Name the app with
     `auth0 apps show <client_id> --json` before you treat a grant as the
     right one.
3. **Merge.** Both writes replace the whole list, so a list built from only
   the new entries silently strips every existing one, and every app relying
   on them breaks. Build the new list as the _before_ list plus the additions.
4. **Show the user the plan and wait for their OK:** the _before_ list, the
   _after_ list, and the exact command.
   - API permissions, keeping each description:
     `auth0 apis update <audience> --data '{"scopes":[…every entry…]}'`
   - Client grant: `auth0 client-grants update <grant-id> --scopes "a,b,c"`
     with the full merged list.
5. **Run it.**
6. **Verify.** Read again and diff against the _before_ snapshot: every
   _before_ entry is still there, and the additions are present. For a grant,
   also mint a token and decode it:
   `auth0 test token <client_id> -a <audience>`, then check that the
   payload's `aud` is the audience and `scope` holds the new entries. Done
   when both checks pass; report any missing entry to the user at once.
