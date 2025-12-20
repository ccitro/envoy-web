# Auth Reverse Engineering Plan (Envoy Web / Enlighten)

Goal: document the login/session flow used by the public Enlighten web UI so we can implement `EnvoyWebTokenManager` (XSRF + auth token acquisition, renewal, and error handling) in `custom_components/envoy_web/api.py`.

- **Developer #1 (CLI‑only)**: uses curl and CLI tools to replay requests.
- **Developer #2 (Browser)**: uses a full browser + DevTools to identify URLs, headers, and response shapes that are hard to infer from curl alone.

---

## 1) Tools & Setup

Developer #1 (CLI‑only):

- `curl` (with `-c` and `-b` for cookie jars)
- `jq` (to inspect JSON responses)
- `sed`, `rg`, `grep` (basic parsing)

Developer #2 (Browser):

- Chrome/Edge with DevTools Network tab.

Shared prerequisites:

- Test account with access to an Enphase IQ Battery.
- Known battery ID + user ID.
- Target URL: `https://enlighten.enphaseenergy.com`.

---

## 2) Discovery Goals (What We Need to Know)

- **Request sequence**: exact order of requests during login and when loading battery profile data.
- **Cookie/token lifecycle**: where XSRF tokens come from and how they refresh.
- **Auth headers**: required headers for `batteryConfig` calls (`e-auth-token`, `x-xsrf-token`, `username`, etc.).
- **Response shapes**: JSON structure for login and profile endpoints.
- **Failure signals**: how expired tokens are reported (status + response body).

---

## 3) Collaboration Flow (CLI + Browser)

### Step A: Developer #2 captures browser flow

Developer #2 uses DevTools to:

1. Log in from a fresh session (clear cookies).
2. Record the login flow in the Network tab (Preserve log on).
3. Navigate to the battery settings page.
4. Filter for `batteryConfig` calls and capture:
   - Request URL
   - Request headers
   - Cookies sent
   - Response JSON

### Step B: Developer #1 asks targeted questions

Developer #1 sends specific questions to Developer #2, for example:

- "What is the exact login POST URL and content type?"
- "Which response contains the `e-auth-token` (header or JSON)?"
- "Is the XSRF token set as a cookie on the initial GET?"
- "What headers are present on the `batteryConfig` GET/PUT requests?"

Developer #2 replies with exact values and sample snippets (sanitized).

---

## 4) CLI Replay Plan (Developer #1)

Developer #1 uses curl to replay the flow using Developer #2’s findings.

### A) Capture initial cookies / XSRF

- Use curl to GET the login page.
- Store cookies in a jar (`-c cookies.txt`).
- Inspect cookies for XSRF token name/value.

### B) Login POST

- Send login POST (URL + payload shape from Developer #2).
- Use same cookie jar (`-b cookies.txt -c cookies.txt`).
- Inspect response headers/body for auth token(s).

### C) Call `batteryConfig`

- Use the gathered headers and cookies.
- GET profile:
  ```
  /service/batteryConfig/api/v1/profile/{BATTERY_ID}?userId={USER_ID}
  ```
- PUT profile with JSON body:
  ```
  {"profile":"self-consumption","batteryBackupPercentage":30}
  ```

If the replay fails, Developer #1 reports exact curl output and asks Developer #2 to confirm:

- Missing headers or cookies
- Incorrect content type
- Required origin/referer headers

---

## 5) Token & Header Map (Build This Together)

Maintain a shared table as findings come in:

| Item | Source | How to Extract | Used In |
|------|--------|----------------|---------|
| XSRF cookie | login GET response | cookie jar | header + cookie |
| `x-xsrf-token` header | derived from cookie | direct copy | GET/PUT |
| `e-auth-token` | login response | header or JSON | GET/PUT |
| `username` header | user ID? | config | GET/PUT |
| session cookies | login flow | cookie jar | GET/PUT |

---

## 6) Expiration / Renewal Behavior

### A) Passive expiration test

- Developer #2 stays logged in and periodically checks the profile request.
- Identify if new tokens are issued or if session renewals occur.

### B) Forced invalidation test

- Developer #2 clears cookies or logs out.
- Replays a `batteryConfig` call to capture failure response.

### C) Failure signature

Record:

- HTTP status (401/403? 302 redirect to login?)
- Response body (JSON vs HTML)
- Whether cookies are cleared or replaced

Developer #1 uses this to implement retry + reauth logic.

---

## 7) Output Deliverables

Developer #2 provides:

- Exact URLs for login GET/POST and profile GET/PUT.
- Required headers and cookies for `batteryConfig`.
- Sample response JSON for login success and profile GET/PUT.
- Failure response examples for expired/invalid tokens.

Developer #1 provides:

- Verified curl replay commands (not code, just the plan outputs).
- Confirmation of the minimum required header/cookie set.

---

## 8) Implementation Guidance (Non‑Code)

Once the above is documented, implement in the API client:

- Fetch XSRF token (likely from cookie in login page response).
- Submit login POST with credentials and XSRF token.
- Extract auth token (header or JSON).
- Cache tokens in memory; invalidate on 401/403.
- Retry once or twice before surfacing auth failure to HA (reauth flow).

---

## 9) Safety / Ethics

- Only use your own credentials.
- Avoid aggressive polling or brute force.
- Keep tokens and cookies private.
