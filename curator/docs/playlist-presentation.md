# Playlist covers and public sharing

Checked 2026-11-17, live-probed 2026-11-19. The static assessment is combined
with live artwork-write probes on throwaway user playlists; no library tracks,
sharing settings, or public URLs were changed. Automated playlist-cover setting
is **unsupported** by Music 1.7 scripting. The documented manual paths remain
the only usable fallback; publication remains unverified.

## Evidence and capability boundary

The installed bundle reports Music **1.7**, build **1.7.0**, in
`/System/Applications/Music.app/Contents/Info.plist`. Its dictionary is
`/System/Applications/Music.app/Contents/Resources/com.apple.Music.sdef`.
These are application resources, not Music-library data.

| Capability | Static evidence | Conclusion |
| --- | --- | --- |
| Playlist artwork | `playlist` declares an `artwork` element (lines 362–366); `user playlist` inherits `playlist` (491). | Declared and readable (count returns 0 for fresh playlists), but **not creatable**: `make new artwork` fails on Music 1.7. |
| Artwork writes | `artwork` (278–286) has `data` (`picture`) and `raw data` (`any`) properties without `access="r"`; its read/write access group is declared. | The dictionary describes writable properties, but live probes show no artwork object can be created. Replacing `data` is only possible if an artwork already exists. |
| Sharing flag | `user playlist.shared` (497), code `pShr`, is a Boolean without `access="r"`; its description asks whether the playlist is shared. | Writable dictionary declaration only. Runtime setter behavior, cloud propagation, and its relationship to the profile/search checkbox are unknown. |
| Playlist cover in the UI | Apple documents editing playlist artwork. | **Manual**, documented; not observed on this machine. |
| Profile/search sharing in the UI | Apple documents the “Show in My Profile and in Search” option. | **Manual**, documented; not observed or enabled here. |
| Public URL and search visibility | Neither the dictionary declarations nor a local success result demonstrate them. | **Unknown / pending live acceptance**; no public-link success may be inferred. |

`track` also declares an `artwork` element (410–414). Track artwork and a playlist
cover are separate targets: changing a song's embedded/album artwork does not
establish playlist-cover support. Existing `curator/src/cover_art.py` and its
tests concern track artwork and provide no playlist-publication evidence.
`playlist.visible` is explicitly read-only and describes sidebar visibility;
it is not public profile or search visibility.

M10 exposes this assessment through
`AppleMusicInterface.get_playlist_presentation_capabilities()` and
`curator playlist-presentation`. Cover reports `manual` with
`automation: unsupported`; sharing still reports `visibility: unknown` and no
public URL. The command does not launch Music, inspect library/account state, or
write anything. `manual` means documented instructions, not verified availability
for the current account. The presentation command itself provides no setter and
no cover-to-playlist mapping. Do not classify automation as supported merely
because a property is present, writable in the dictionary, or succeeds for a
track.

## Manual cover workflow

After the actual target and artwork have been reviewed and changing Music has
been explicitly authorized:

1. Select the intended playlist in Music's sidebar.
2. Open the playlist's More menu and choose Edit.
3. In the Edit Playlist sheet, click the artwork Add control and choose the
   reviewed image (or drag it into the artwork area).
4. Click Done and inspect the resulting playlist cover.

Apple documents this separately from Song → Get Info → Artwork, which edits
song artwork. These are instructions for a later manual action, not steps run
during this assessment. See [Add artwork to content in Music on Mac](https://support.apple.com/en-mt/guide/music/mus1c6803257/mac).

## Cover automation (unsupported, preview remains read-only)

`curator playlist-cover --playlist-id ID --image PATH` validates the PNG/JPEG
file, reads the playlist name and artwork count, and prints a SHA-256 of the
image without changing anything. `--apply --yes` is refused before Music is
contacted and prints the manual UI steps above.

Live probes on 2026-11-19 used a throwaway user playlist with Music 1.7. Reading
`count of artworks` worked (returned 0). Every creation path failed:
`make new artwork at end of artworks` returned `-10014` ("Handler only handles
single objects") or `-2710` ("Can't make class artwork"), `raw data` and `data`
variants failed identically, and `duplicate`/`copy` of a track artwork either
errored or left the playlist at zero artworks. This matches the long-standing
limitation that iTunes/Music exposes artwork for reading and replacing only
when an object already exists; it does not create artwork objects. GUI scripting
can reach the Edit Playlist sheet, but it depends on Accessibility permission,
English/localized menu names and window state, so it is not shipped as an
automated setter. Sharing and public visibility are untouched; a manual cover
edit is not a publication and does not produce a public URL.

## Manual sharing workflow and prerequisites

Apple describes creating an Apple Music profile after subscribing to Apple
Music. Profile setup, the intended audience, region availability, and applicable
age/parental restrictions must be reviewed by the user; their account status is
unknown here. Profile setup can also expose selected playlists/listening
activity, so it requires its own informed choice. See [Create an Apple Music
profile on Mac](https://support.apple.com/en-za/guide/music/mus3a76cdc0/mac).

Once the target, audience, and sharing action are explicitly authorized, select
the playlist, click Edit (or More → Edit), and select “Show in My Profile and in
Search.” Apple also documents Control-clicking the playlist → Edit to reach
this option. Profile → Music Profile → Edit → Shared Playlists is another
documented selection path. See [Create, edit, and delete playlists in Music on
Mac](https://support.apple.com/en-mt/guide/music/musd5d051981/mac) and [Share music
with friends on Mac](https://support.apple.com/en-sg/guide/music/mus140a2e93/mac).

Profile audience controls matter: sharing with approved followers and choosing
a public audience are separate decisions. Sending a playlist link, profile
listing, public search discovery, and collaborative editing are also distinct
outcomes. A local `shared = true` value must not be equated with all of them.
Apple's UI documentation does not establish that `shared` implements the named
checkbox, supplies a public URL, or guarantees immediate cloud/search updates.

## Review required before a later pilot

Prepare a preview identifying one actual playlist unambiguously, the exact
cover file and rendered crop, its name/description, and the requested audience
and publication outcome. The user must choose the target and cover direction;
no mapping or target is assumed here. Review current cover/sharing state and a
restoration approach only after library/account inspection is authorized.
Obtain explicit authorization for the concrete writes and any public exposure
before applying them; static research is not that authorization.

A later cover proposal would need a supported setter (for example a future
Music API or a separately verified GUI helper) plus isolated evidence and
preview/apply tests; none exists today. A pilot must separately observe the
displayed cover, persistence, relevant cloud behavior, and the actual share URL
and intended audience visibility. Public profile/search visibility
requires its own observation; a successful local write or copied link alone
does not prove it. Record failures and unknown propagation rather than claiming
publication. All live acceptance remains pending.

## Source verification limits

The local dictionary and bundle metadata were read directly as static files.
The official artwork, profile, and friends-sharing pages were accessible.
The exact playlist guide above returned HTTP 429 on direct opening; its relevant
Edit/artwork/profile instructions were independently available in the search
service's indexed official Apple page (reported crawled two weeks earlier).
Current Apple guides can differ by locale, macOS version, and account state;
none substitutes for later observation on the chosen target.
