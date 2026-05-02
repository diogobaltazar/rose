# Auth0 Setup for tgun.dev

## 1. Create an Application

In the [Auth0 Dashboard](https://manage.auth0.com/) → **Applications → Applications → Create Application**:

- **Name:** `topgun`
- **Type:** Single Page Application

---

## 2. Configure Allowed URLs

In the application settings, set all three fields:

| Field | Value |
|---|---|
| Allowed Callback URLs | `http://localhost:5100/callback, https://tgun.dev/callback` |
| Allowed Logout URLs | `http://localhost:5100, https://tgun.dev` |
| Allowed Web Origins | `http://localhost:5100, https://tgun.dev` |

Save changes.

---

## 3. Create an API (Audience)

In **Applications → APIs → Create API**:

- **Name:** `topgun-api`
- **Identifier:** `https://tgun.dev/api` *(this becomes your `AUTH0_AUDIENCE`)*
- **Signing Algorithm:** RS256

---

## 4. Collect Your Credentials

From the application **Settings** tab:

| Variable | Where to find it |
|---|---|
| `AUTH0_DOMAIN` | **Domain** field, e.g. `your-tenant.eu.auth0.com` |
| `AUTH0_CLIENT_ID` | **Client ID** field |
| `AUTH0_AUDIENCE` | The **Identifier** you set in step 3 |

---

## 5. Set the Variables

### Locally (docker compose)

Create a `.env` file at the repo root (already in `.gitignore`):

```bash
AUTH0_DOMAIN=your-tenant.eu.auth0.com
AUTH0_CLIENT_ID=your-client-id
AUTH0_AUDIENCE=https://tgun.dev/api
```

Then:

```bash
docker compose up --build
```

The webapp is at `http://localhost:5100`.

### Remote (tgun.dev)

Set the same three variables in your hosting environment's secret store.  
The same Docker image is used — no rebuild needed when switching between local and remote.

---

## 6. Dev Mode (no Auth0)

If `AUTH0_DOMAIN` is not set, the API skips JWT validation and all endpoints are open.  
Useful for local development without an internet connection.

```bash
# omit AUTH0_* vars entirely — the app still loads but skips authentication
docker compose up --build
```
