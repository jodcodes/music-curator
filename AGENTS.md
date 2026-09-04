# Music Curator agent guidance

This monorepo contains independent Apple Music and Spotify tools. Keep changes within the owning subproject unless shared behavior genuinely belongs at the root.

## Safety

- Commands that touch Music.app, Spotify, IMAP, playlists, tags, launchd, or state files can mutate real user data. Use dry-run or preview modes unless the user explicitly requests applying changes.
- Never run `--apply`, `--force`, authentication, email-trash, bulk-cleanup, sync wrappers, or LaunchAgent installation as verification.
- Never commit `.env`, OAuth tokens, credentials, local databases, logs, caches, or Music-library data.
- Preserve the contract that destructive operations default to preview and require explicit opt-in.

## Checks

- Root smoke test: `python3 music_curator.py --list`.
- Curator safe tests: from `curator/`, run the focused pytest file for the change; CI's safe set is documented in `.github/workflows/ci.yml`.
- Apple-to-Spotify tests: `python3 -m pytest apple2spfy/tests`.
- Pitch2play: from `pitch2play/`, run `npm test` and `npm run lint`.
- Music-tools tests: run the relevant files under `music_tools/tests/` without invoking `music_tools/bin/run_all.sh`.
