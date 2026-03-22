---
name: github-pat-creation
description: Use this skill when Claude is suggesting that the user should create a GitHub PAT (personal access token), or when the user asks about creating a new GitHub PAT.
version: 0.1.0
---

# GitHub Personal Access Token URL Creator

## Purpose

Generate pre-filled GitHub Personal Access Token (PAT) creation URLs that
streamline the token setup process by automatically populating appropriate
permissions, descriptions, and expiration settings based on the user's needs.

## When to Use This Skill

Use this skill in these scenarios:

1. **Proactive suggestion**: When the current workflow requires GitHub authentication and a PAT would be appropriate
2. **Direct request**: When the user explicitly asks for help creating a GitHub token
3. **Permission guidance**: When the user needs clarification on what permissions their token should have
4. **Workflow automation**: When setting up CI/CD, scripts, or tools that need GitHub access

## Decision Framework

### When Sufficient Context Exists

If the conversation or task provides clear indication of the scope of access
required then proceed directly to crafting the appropriate PAT URL without
additional prompts.

### When Context is Unclear

If the purpose or required permissions are ambiguous, offer assistance:

```
I can help you create a GitHub Personal Access Token. Just let me know what you need it for.
```

Gathering context may or may not take more than one turn.

## Crafting PAT URLs

### URL Structure

All GitHub PAT URLs follow this base pattern:

```
https://github.com/settings/personal-access-tokens/new?param1=value1&param2=value2
```

### Core Parameters

1. **name** - Token display name (URL-encoded, ≤40 chars)
2. **description** - Purpose explanation (URL-encoded, ≤1024 chars)
3. **target_name** - User/org slug (optional, defaults to current user)
4. **expires_in** - Days until expiration (1-366) or `none`
5. **permissions** - One or more permission parameters

## Permission Parameters

You can share templates for a PAT via links. 

Each supported field can be set using a specific query parameter. All
parameters are optional and validated by the token generation form to ensure
that the combinations of permissions and resource owner makes sense.

An example URL template is shown here, with line breaks for legibility:

```http copy
https://github.com/settings/personal-access-tokens/new
  ?name=Repo-reading+token
  &description=Just+contents:read
  &target_name=octodemo
  &expires_in=45
  &contents=read
```

Try the URL to create a token with `contents:read` and `metadata:read`, with the given name and description and an expiration date 45 days in the future. You'll see an error message indicating `Cannot find the specified resource owner: octodemo` because you're not a member of the `octodemo` organization.

Below are some example URLs that generate the tokens we see most often:

* [Read repo contents](https://github.com/settings/personal-access-tokens/new?name=Repo-reading+token&description=Just+contents:read&contents=read)
* [Push access to repos](https://github.com/settings/personal-access-tokens/new?name=Repo-writing+token&description=Just+contents:write&contents=write)
* [GitHub Models access](https://github.com/settings/personal-access-tokens/new?name=GitHub+Models+token&description=Used%20to%20call%20GitHub%20Models%20APIs%20to%20easily%20run%20LLMs%3A%20https%3A%2F%2Fdocs.github.com%2Fgithub-models%2Fquickstart%23step-2-make-an-api-call&user_models=read)<!-- markdownlint-disable-line search-replace Custom rule -->
* [Update code and open a PR](https://github.com/settings/personal-access-tokens/new?name=Core-loop+token&description=Write%20code%20and%20push%20it%20to%20main%21%20Includes%20permission%20to%20edit%20workflow%20files%20for%20Actions%20-%20remove%20%60workflows%3Awrite%60%20if%20you%20don%27t%20need%20to%20do%20that&contents=write&pull_requests=write&workflows=write)
* [Manage Copilot licenses in an organization](https://github.com/settings/personal-access-tokens/new?name=Core-loop+token&description=Enable%20or%20disable%20copilot%20access%20for%20users%20with%20the%20Seat%20Management%20APIs%3A%20https%3A%2F%2Fdocs.github.com%2Frest%2Fcopilot%2Fcopilot-user-management%0ABe%20sure%20to%20select%20an%20organization%20for%20your%20resource%20owner%20below%21&organization_copilot_seat_management=write)<!-- markdownlint-disable-line search-replace Custom rule -->

#### Supported Query Parameters

To create your own token template, follow the query parameter details provided in this table:

| Parameter      | Type    | Example Value          | Valid Values                              | Description                                                                                                                                                             |
|----------------|---------|------------------------|-------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `name`         | string  | `Deploy%20Bot`         | ≤ 40 characters, URL-encoded              | Pre-fills the token’s display name.                                                                                                                                     |
| `description`  | string  | `Used+for+deployments` | ≤ 1024 chars, URL-encoded                 | Pre-fills the description for the token.                                                                                                                                |
| `target_name`  | string  | `octodemo`             | User or organization slug                 | Sets the token's resource target. This is the owner of the repositories that the token will be able to access. If not provided, defaults to the current user's account. |
| `expires_in`   | integer | `30` or `none`         | Integer between 1 and 366, or `none`      | Days until expiration or `none` for non-expiring. If not provided, the default is 30 days, or less if the target has a token lifetime policy set.                       |
| `<permission>` | string  | `contents=read`        | A series of permission and access levels. | The permissions the token should have. Permissions can be set to `read`, `write`, or `admin`, but not every permission supports each of those levels.                   |

#### Permissions

Each supported permission is set using its name as a query parameter, with the value specifying the desired access level. Valid access levels are `read`, `write`, and `admin`. Some permissions only support `read`, some only support `write`, and only a few have `admin`. Use as many permissions as needed, in the form `&contents=read&pull_requests=write&...`.

You do not need to include both `read` and `write` for a permission in your URL—`write` always includes `read`, and `admin` always includes `write`.

##### Account Permissions

Account permissions are only used when the current user is set as the resource owner.

| Parameter name                   | Display name                   | Access levels   |
|----------------------------------|--------------------------------|-----------------|
| `blocking`                       | Block another user             | `read`, `write` |
| `codespaces_user_secrets`        | Codespaces user secrets        | `read`, `write` |
| `copilot_messages`               | Copilot Chat                   | `read`          |
| `copilot_editor_context`         | Copilot Editor Context         | `read`          |
| `emails`                         | Email addresses                | `read`, `write` |
| `user_events`                    | Events                         | `read`          |
| `followers`                      | Followers                      | `read`, `write` |
| `gpg_keys`                       | GPG keys                       | `read`, `write` |
| `gists`                          | Gists                          | `write`         |
| `keys`                           | Git SSH keys                   | `read`, `write` |
| `interaction_limits`             | Interaction limits             | `read`, `write` |
| `knowledge_bases`                | Knowledge bases                | `read`, `write` |
| `user_models`                    | Models                         | `read`          |
| `plan`                           | Plan                           | `read`          |
| `private_repository_invitations` | Private repository invitations | `read`          |
| `profile`                        | Profile                        | `write`         |
| `git_signing_ssh_public_keys`    | SSH signing keys               | `read`, `write` |
| `starring`                       | Starring                       | `read`, `write` |
| `watching`                       | Watching                       | `read`, `write` |

##### Repository Permissions

Repository permissions work for both user and organization resource owners.

| Parameter name                 | Display name                   | Access levels   |
|--------------------------------|--------------------------------|-----------------|
| `actions`                      | Actions                        | `read`, `write` |
| `administration`               | Administration                 | `read`, `write` |
| `artifact_metadata`            | Artifact Metadata              | `read`, `write` |
| `attestations`                 | Attestations                   | `read`, `write` |
| `security_events`              | Code scanning alerts           | `read`, `write` |
| `codespaces`                   | Codespaces                     | `read`, `write` |
| `codespaces_lifecycle_admin`   | Codespaces lifecycle admin     | `read`, `write` |
| `codespaces_metadata`          | Codespaces metadata            | `read`          |
| `codespaces_secrets`           | Codespaces secrets             | `write`         |
| `statuses`                     | Commit statuses                | `read`, `write` |
| `contents`                     | Contents                       | `read`, `write` |
| `repository_custom_properties` | Custom properties              | `read`, `write` |
| `vulnerability_alerts`         | Dependabot alerts              | `read`, `write` |
| `dependabot_secrets`           | Dependabot secrets             | `read`, `write` |
| `deployments`                  | Deployments                    | `read`, `write` |
| `discussions`                  | Discussions                    | `read`, `write` |
| `environments`                 | Environments                   | `read`, `write` |
| `issues`                       | Issues                         | `read`, `write` |
| `merge_queues`                 | Merge queues                   | `read`, `write` |
| `metadata`                     | Metadata                       | `read`          |
| `pages`                        | Pages                          | `read`, `write` |
| `pull_requests`                | Pull requests                  | `read`, `write` |
| `repository_advisories`        | Repository security advisories | `read`, `write` |
| `secret_scanning_alerts`       | Secret scanning alerts         | `read`, `write` |
| `secrets`                      | Secrets                        | `read`, `write` |
| `actions_variables`            | Variables                      | `read`, `write` |
| `repository_hooks`             | Webhooks                       | `read`, `write` |
| `workflows`                    | Workflows                      | `write`         |
