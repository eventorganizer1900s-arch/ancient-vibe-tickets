# Ancient Event — flat-file deployment

This version has **no folders**. The page templates and CSS are embedded directly inside `app.py`.

## Files
- `app.py`
- `requirements.txt`
- `render.yaml`
- `README.md`
- `.gitignore`

## Deploy on Android using GitHub and Render
1. Extract this ZIP on your phone.
2. Create a GitHub repository, for example `ancient-event-tickets`.
3. Upload these five files directly to the repository root. Do not upload the ZIP itself.
4. In Render, choose New + → Blueprint and connect the repository.
5. Set a strong `ADMIN_PASSWORD` (10+ characters) when asked. Keep it private.
6. Deploy and wait for Live. Sign in at the Render URL with the configured username and password.
7. Test: generate a ticket, verify once (accepted), verify again (already used), then try an unknown ID (invalid).

The Blueprint creates a PostgreSQL database named `ancient-event-db`. If you already use a different database, change the database name in `render.yaml` or set `DATABASE_URL` manually in Render.

Camera scanning requires HTTPS and camera permission. Keep secrets out of GitHub. If the database already has an admin account, changing `ADMIN_PASSWORD` later will not reset that existing account's password.
