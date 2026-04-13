## URL Health Check

A monthly automated check that pings every recipe URL in the database and flags any that are broken or unreachable.

### How it works
- Vercel runs the check automatically at midnight UTC on the 1st of every month
- Results are saved to `app/cron/health_report.json` and displayed at `/url-health-status`
- The check can also be triggered manually (see below)

### Viewing results
Navigate to `/url-health-status` to see the latest report including total recipes checked, flagged URLs, and the timestamp of the last run.

### Manual trigger
To force a fresh run outside of the scheduled job:
```bash
curl -H "Authorization: Bearer your_cron_secret" https://yourapp.vercel.app/cron/url-health
```
Locally, no auth header is needed — just visit `http://localhost:5000/cron/url-health` in your browser.

### Environment variables
| Variable | Description |
|---|---|
| `CRON_SECRET` | Bearer token Vercel sends with each cron request. Prevents unauthorized manual triggers in production. Generate with `python -c "import secrets; print(secrets.token_hex(16))"` |

### Status codes
| Code | Treatment |
|---|---|
| `200` | ✅ Healthy |
| `403` / `429` | ✅ Healthy (server alive, access restricted) |
| `404` / `410` / `500`+ | ❌ Flagged |
| Timeout / Unreachable | ❌ Flagged |
