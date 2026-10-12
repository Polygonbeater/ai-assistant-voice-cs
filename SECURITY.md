# Security Policy

## Reporting a vulnerability

Please report security issues **privately** to info@polygonbeater.eu (subject: "Security report").
Do not open a public issue for vulnerabilities. We aim to acknowledge reports within 7 days.

## Scope and threat model

Polygon Beater is a **local-first desktop tool**, not a network service. It is designed to be
reachable from the local machine only.

| Layer | What it protects | What it does NOT protect |
|---|---|---|
| Network Loopback Shield (all `/api/` endpoints, `Host` header check) | The local API from other devices on the network and from DNS-rebinding web pages | A local user or process that can already reach `127.0.0.1:8000` |
| `X-Polygon-Client: true` header on mutating requests | Cross-site request forgery from websites in the browser | It is a marker, **not authentication** |
| Blender bridge auth token (`blender.auth_token` / `POLYGON_BLENDER_AUTH_TOKEN`) | Port 9876 from other local processes that do not know the token. The bridge refuses to start without a token | Anyone who can read your `config.json` or environment |
| AST code validator (module whitelist, banned builtins, save/import/export blocked) | Blocks obviously dangerous constructs before code reaches Blender | **It is not a sandbox.** `bpy` is the full Blender API |
| Human-in-the-loop diff for `write_file` | Unreviewed writes to your project directory | Content you approve |

## Data leaving your machine

In the default local mode, inference and project data stay on your machine. If you enable an external
provider (Groq, Gemini, any OpenAI-compatible endpoint) or web research (DuckDuckGo), the content of
the request is sent to that service.

## Recommendations

- Do not expose the server on a public address or behind a reverse proxy.
- Keep `config.json` permissions restricted and never commit the token.
- Work on copies of important `.blend` files.
