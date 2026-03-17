---
name: qapi-create-tests
description: >
  Generate and save QAPI-format API tests to the Qyrus QAPI platform. Use when the user explicitly
  wants to scan HTTP API routes or OpenAPI specs, create QAPI test payloads, list QAPI teams or
  workspaces, or publish tests into a QAPI workspace with the bundled client and QAPI_* environment
  variables. Do not use for generic unit-test, integration-test, or framework-specific test creation
  unless the request is specifically about QAPI or Qyrus API test assets.
---

# QAPI Test Creation Skill

QAPI is the Qyrus API testing platform. This skill scans a codebase for API endpoints, generates
complete QAPI-format test objects with assertions and schema validations, then saves them to a chosen
QAPI workspace via the REST API — all without leaving the editor.

## Workflow Overview

| Stage | What happens |
|---|---|
| **Preflight** | Verify env vars and determine the target QAPI environment |
| **Discover** | Scan routes, controllers, and OpenAPI specs for endpoints |
| **Generate** | Produce a full QAPI test JSON object per endpoint, including assertions |
| **Teams** | Fetch the user's teams via `scripts/qapi_client.py get-teams` |
| **Workspaces** | List workspaces and ask the user which one to save into |
| **Save** | Create a placeholder per test to get a server UUID, then POST the full test |
| **Report** | Print a summary table of saved / failed tests |

## Core Concepts

### Environment Variables

All three required variables must be set before the workflow starts:

| Variable | Header sent | Required |
|---|---|---|
| `QAPI_API_TOKEN` | `X-API-Key` | Yes |
| `QAPI_GATEWAY_TOKEN` | `Authorization: Bearer` | Yes |
| `QAPI_USER_EMAIL` | `Login` | Yes |
| `QAPI_APP_URL` | _(used for routing)_ | No — defaults to `qapi.qyrus.com` |

All bundled client requests also send a fixed header: `scope: AI_SDK`.

### Supported Environments

| `QAPI_APP_URL` | Gateway | Path prefix |
|---|---|---|
| `qapi.qyrus.com` (default) | `api-pc-gateway.qyrus.com` | `/api-marketplace/` |
| `stg-api.qyrus.com` | `stg-gateway.qyrus.com:8243` | `/api-marketplace-qapi/` |

If `QAPI_APP_URL` is anything else, stop and tell the user it is unsupported until the gateway and
path mapping are confirmed.

### Python Client

All API calls go through `scripts/qapi_client.py`. It reads env vars automatically and prints JSON
to stdout:

```bash
python scripts/qapi_client.py new-suite-id
python scripts/qapi_client.py get-teams
python scripts/qapi_client.py get-workspaces --team-id <UUID>
python scripts/qapi_client.py create-placeholder --team-id <UUID> --workspace-id <UUID> --name <str> --suite-id <UUID>
python scripts/qapi_client.py save-test --team-id <UUID> --workspace-id <UUID> --test-json <JSON> --suite-id <UUID>
```

### Assertion Types

**`assertBodies.type`** — only two valid values:

| Type | When to use |
|---|---|
| `CONTAINS` | Response body text includes this value (use for field names, resource types, status strings) |
| `DOES_NOT_CONTAIN` | Response body must not include this value (use sparingly, e.g. to assert secrets are absent) |

**`assertJsonPaths.type`** — pick the most appropriate for each field:

| Type | When to use | `value` field |
|---|---|---|
| `NOT_NULL` | Field must exist and be non-null | `""` (empty) |
| `CONTAINS` | String field contains a substring | the substring |
| `DOES_NOT_CONTAIN` | String field must not contain a substring | the substring |
| `EQUAL_TO` | Field equals an exact value | the exact value |
| `NOT_EQUAL_TO` | Field must differ from a value | the value to differ from |
| `GREATER_THAN` | Numeric field exceeds a threshold | the threshold (as string) |
| `LESSER_THAN` | Numeric field is below a threshold | the threshold (as string) |
| `REGULAR_EXPRESSION` | Field matches a regex pattern | the regex pattern |

### Create-Then-Save Pattern

New tests require one shared `suiteId` and **two API calls**:
1. `new-suite-id` → generate a suite UUID for the current run or current test
2. `create-placeholder` → server assigns a UUID and `sequenceId`
3. `save-test` → POST the full test object with that UUID injected as `"id"` and the same `suiteId`

Never skip the placeholder step, and never switch `suiteId` between placeholder creation and save.

---

## Execution Workflow

Follow every step in order. Run each shell command and parse its output before continuing.

### Step 0 — Preflight Checks

```bash
echo "API_TOKEN=${QAPI_API_TOKEN:+set} GATEWAY_TOKEN=${QAPI_GATEWAY_TOKEN:+set} EMAIL=${QAPI_USER_EMAIL:+set} APP_URL=${QAPI_APP_URL:-qapi.qyrus.com}"
```

If any of `QAPI_API_TOKEN`, `QAPI_GATEWAY_TOKEN`, or `QAPI_USER_EMAIL` are missing (shown as blank,
not "set"), stop and tell the user which variables need to be configured. Do not proceed until all
three are present. If `QAPI_APP_URL` is set, it must be one of the supported hostnames above.

### Step 1 — Discover Endpoints

Scan the user's codebase (or the files/folders they specified) for API endpoints. Look for:
- Route definitions (Express, FastAPI, Django, Spring, Rails, Gin, etc.)
- Controller methods with HTTP verb annotations (`@GetMapping`, `@app.post`, `router.get`, etc.)
- OpenAPI/Swagger spec files (`openapi.yaml`, `swagger.json`, etc.)
- GraphQL only when it is exposed through an HTTP endpoint you can represent as a REST request

Skip raw gRPC or non-HTTP interfaces. This skill produces `apiType: "REST"` QAPI payloads.

For each endpoint, collect:

| Field | Description |
|---|---|
| `name` | Short descriptive name (max 60 chars, alphanumeric + spaces/hyphens/underscores) |
| `method` | HTTP verb: GET, POST, PUT, DELETE, PATCH |
| `url` | Full URL or URL pattern (substitute example values for path params) |
| `description` | What this endpoint does |
| `requestBody` | Expected request body for POST/PUT/PATCH, or `null` |
| `headers` | Required request headers beyond Content-Type |
| `params` | Query parameters |
| `expectedResponse` | Shape of a successful response — drives assertion generation |

If no endpoints are found, tell the user and ask them to point you to the relevant files.

### Step 2 — Generate QAPI Test JSON

For each discovered endpoint, produce a complete QAPI test object:

```json
{
  "name": "<descriptive name, max 60 chars>",
  "method": "GET|POST|PUT|DELETE|PATCH",
  "apiType": "REST",
  "protocol": "https",
  "host": "",
  "port": "",
  "contextPath": "/",
  "description": "<what this endpoint does>",
  "url": "<full URL>",
  "urlEncodeEnabled": true,
  "timeout": 300,
  "isActive": true,
  "scriptType": "PLAYGROUND",
  "sequenceId": null,

  "requestBody": {
    "type": "JSON",
    "content": "<stringified JSON — must be a string, never a raw object>",
    "isParameterized": false
  },

  "headers": [
    {
      "key": "Content-Type",
      "value": "application/json",
      "description": null,
      "isActive": true,
      "isParameterized": false,
      "isAuth": false,
      "isMasked": true
    }
  ],

  "params": [],
  "formData": [],
  "authorizations": [],
  "certUuid": null,
  "certificateId": null,
  "variableName": null,
  "isBodyParameterized": false,
  "isChaining": false,
  "chainingConfigration": null,
  "isParameterized": false,
  "parameterizedType": null,
  "parameterizedFileName": null,
  "databaseAssertions": [],
  "databaseInfo": null,
  "assertOnResponseBody": false,
  "isDatabaseAssertion": false,
  "databaseStatement": "",
  "dataHandlers": [],
  "assertResponseStatus": [],
  "assertJavascripts": [],
  "assertXpaths": [],

  "assertHeaders": [
    {
      "key": "Content-Type",
      "value": "application/json",
      "description": "Response should return JSON",
      "isParameterized": false,
      "isActive": true,
      "isAIGenerated": true,
      "isConditional": false
    }
  ],

  "assertBodies": [
    {
      "value": "<key term from expected response>",
      "key": null,
      "type": "CONTAINS",
      "description": "Response body should contain <key term>",
      "isParameterized": false,
      "isActive": true,
      "isAIGenerated": true,
      "isConditional": false
    }
  ],

  "assertJsonPaths": [
    {
      "jsonPath": "$.<required field path>",
      "key": null,
      "value": "",
      "isConditional": false,
      "type": "NOT_NULL",
      "isAIGenerated": true,
      "isParameterized": false,
      "isActive": true,
      "description": "<field> should be present"
    },
    {
      "jsonPath": "$.<string field path>",
      "key": null,
      "value": "<expected substring>",
      "isConditional": false,
      "type": "CONTAINS",
      "isAIGenerated": true,
      "isParameterized": false,
      "isActive": true,
      "description": "<field> should contain expected value"
    },
    {
      "jsonPath": "$.<exact field path>",
      "key": null,
      "value": "<expected exact value>",
      "isConditional": false,
      "type": "EQUAL_TO",
      "isAIGenerated": true,
      "isParameterized": false,
      "isActive": true,
      "description": "<field> should equal expected value"
    }
  ],

  "schemaValidations": [
    {
      "schemaContent": "{\"type\":\"object\",\"properties\":{}}",
      "schemaVersion": "VERSION_1",
      "key": null,
      "isParameterized": false,
      "isActive": true,
      "isAIGenerated": true,
      "schemaType": "JSON"
    }
  ]
}
```

**Generation rules:**
- If the endpoint has query parameters, keep them out of `url` and populate `params` with active
  entries shaped like:
  `{"key":"page","value":"1","paramType":"QUERY","isParameterized":false,"isAuth":false,"isActive":true}`
- Include only active, non-empty `headers`, `params`, and `formData` rows.
- `requestBody.content` must always be a **string**. Set `requestBody` to `null` for GET/DELETE with no body.
- If `requestBody.content` starts as an object, stringify it before saving.
- `assertBodies`: generate 1–3 `CONTAINS` entries using key terms from the expected response. Use `DOES_NOT_CONTAIN` only when the endpoint must explicitly exclude a value (e.g. passwords, internal IDs).
- `assertJsonPaths`: cover 2–5 important fields — `NOT_NULL` for required IDs/objects, `EQUAL_TO` for known fixed values, `GREATER_THAN`/`LESSER_THAN` for numeric/pagination fields.
- `schemaValidations.schemaContent`: stringified JSON Schema describing the expected response shape.
- Do not include `id` fields in nested arrays — the server assigns those on save.
- If `params` are present, strip the query string from `url` to avoid duplicating the same values in both places.

Store the generated tests for use in later steps.

### Step 3 — Fetch Teams

```bash
python scripts/qapi_client.py get-teams
```

Use the **first team's `uuid`** as `TEAM_ID` for all subsequent calls. Tell the user which team was
selected (teamName + uuid). Stop and show the error if this command fails.

### Step 4 — Fetch Workspaces and Ask User

```bash
python scripts/qapi_client.py get-workspaces --team-id <TEAM_ID>
```

Display the workspace list as a numbered table:

| # | Name | ID | Type |
|---|---|---|---|

Ask the user: **"Which workspace should the tests be saved to? Enter the number or workspace name."**

Wait for their response, then store the selected workspace's `id` as `WORKSPACE_ID`.

### Step 5 — Create and Save Each Test

For each generated test:

**5a — Generate a shared suite UUID for the placeholder/save pair:**
```bash
python scripts/qapi_client.py new-suite-id
```
Capture the returned `suiteId` and reuse it for both of the next calls. If you are saving multiple
tests in one run, you may reuse the same `suiteId` across the entire batch.

**5b — Create placeholder** (gets a server-assigned UUID):
```bash
python scripts/qapi_client.py create-placeholder \
  --team-id <TEAM_ID> \
  --workspace-id <WORKSPACE_ID> \
  --name "<test name>" \
  --suite-id <SUITE_ID>
```
Extract `id` and `sequenceId` from the response. If this fails, mark the test FAILED and continue —
do not abort the entire run.

**5c — Inject server ID and save full test:**

Set `"id"` and `"sequenceId"` in the test JSON from the values in 5b, then:
```bash
python scripts/qapi_client.py save-test \
  --team-id <TEAM_ID> \
  --workspace-id <WORKSPACE_ID> \
  --suite-id <SUITE_ID> \
  --test-json '<full test JSON as a single-line string>'
```
If the response contains the test `id`, mark as SAVED. Otherwise mark as FAILED and include the error.

### Step 6 — Report

Print a summary table:

| Test Name | Method | URL | Status |
|---|---|---|---|
| Get Users | GET | /api/users | ✓ Saved |
| Create Order | POST | /api/orders | ✓ Saved |
| Delete Item | DELETE | /api/items/:id | ✗ Failed: \<error\> |

Tell the user how many tests saved successfully, the workspace name, and to verify in QAPI at the app URL.

---

## Guidelines

1. **Always run preflight first** — missing env vars will cause every API call to fail with an unhelpful error
2. **Scan broadly, then confirm** — list discovered endpoints before generating JSON so the user can correct scope
3. **Use the assertion type table** — never invent assertion type strings; only use values from the tables above
4. **Stringify request bodies** — `requestBody.content` must be a string even when the body is JSON
5. **Never skip create-placeholder** — `save-test` without a server-assigned UUID will be rejected
6. **Keep one suite ID per save flow** — reuse the same `suiteId` for placeholder creation and the subsequent save
7. **Fail per test, not per run** — if one test's placeholder or save fails, log it and continue with the rest
8. **Keep test names under 60 chars** — the server enforces this limit; truncate and append `...` if needed
