// Contract tests for find_playlist_duplicates.js.
//
// The real script only runs under `osascript -l JavaScript` against a live
// Music.app library. To test its duplicate-resolution and error-propagation
// logic without touching Apple Music, this loads the script source into a
// Node `vm` context with fakes for Application/ObjC/$ standing in for the
// JXA bridge, then calls the script's top-level `run(argv)` directly.
//
// Run: node --test music_tools/tests/test_find_playlist_duplicates.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCRIPT_PATH = path.join(__dirname, "..", "scripts", "find_playlist_duplicates.js");
const SCRIPT_SOURCE = fs.readFileSync(SCRIPT_PATH, "utf8");

function makeTrackList(tracksMeta, { failBulk = false } = {}) {
    const bulk = (key) => () => {
        if (failBulk) throw new Error("Can't get object.");
        return tracksMeta.map((t) => t[key]);
    };
    const base = {
        name: bulk("name"),
        artist: bulk("artist"),
        persistentID: bulk("id"),
        dateAdded: bulk("added"),
        cloudStatus: bulk("cloud"),
        length: tracksMeta.length,
    };
    return new Proxy(base, {
        get(target, prop) {
            if (prop in target) return target[prop];
            if (typeof prop === "string" && /^\d+$/.test(prop)) {
                const idx = Number(prop);
                const meta = tracksMeta[idx];
                if (!meta) return undefined;
                return {
                    _idx: idx,
                    name: () => {
                        if (meta.broken && meta.brokenProp === "name") throw new Error("broken name");
                        return meta.name;
                    },
                    artist: () => {
                        if (meta.broken && meta.brokenProp === "artist") throw new Error("broken artist");
                        return meta.artist;
                    },
                    persistentID: () => {
                        if (meta.broken && meta.brokenProp === "id") throw new Error("broken id");
                        return meta.id;
                    },
                    dateAdded: () => meta.added,
                    cloudStatus: () => meta.cloud,
                };
            }
            return undefined;
        },
    });
}

function makePlaylist({ name, smart = false, specialKind = "", tracksMeta, failBulk = false }) {
    return {
        name: () => name,
        smart: () => smart,
        specialKind: () => specialKind,
        tracks: makeTrackList(tracksMeta, { failBulk }),
    };
}

function buildSandbox(playlists, { deleteShouldFailForIndex = new Set() } = {}) {
    const deletions = [];
    const shellLog = [];

    // Real Music.delete() removes by specifier/position; it never needs to
    // read a track's persistentID first (a broken track must still be
    // deletable by its playlist position).
    const Music = {
        includeStandardAdditions: false,
        timeout: 60,
        userPlaylists: () => playlists,
        delete: (trackRef) => {
            if (deleteShouldFailForIndex.has(trackRef._idx)) {
                throw new Error(`delete failed for index ${trackRef._idx}`);
            }
            deletions.push(trackRef);
        },
    };

    const App = {
        includeStandardAdditions: false,
        doShellScript: (cmd) => {
            if (cmd.includes("pmset")) return "AC Power";
            shellLog.push(cmd);
            return "";
        },
    };

    const sandbox = {
        ObjC: { import: () => {} },
        Application: Object.assign((name) => (name === "Music" ? Music : App), {
            currentApplication: () => App,
        }),
        $: {
            NSHomeDirectory: () => ({ js: "/tmp/fake-home" }),
            NSFileManager: { defaultManager: { fileExistsAtPath: () => true } },
            NSThread: { sleepForTimeInterval: () => {} },
        },
    };
    vm.createContext(sandbox);
    vm.runInContext(SCRIPT_SOURCE, sandbox, { filename: "find_playlist_duplicates.js" });
    return { sandbox, deletions, shellLog };
}

test("fallback: track with broken persistent ID is excluded from duplicate comparison entirely", () => {
    // idx1 is "broken" (persistentID throws) but shares name/artist with idx0,
    // and its dateAdded sorts EARLIER than idx0's. Under the buggy behavior
    // this makes the broken entry win as "keeper" and the good track at idx0
    // gets scheduled for deletion. A track with no readable persistent ID
    // must never participate in duplicate comparisons at all.
    const tracksMeta = [
        { name: "Song", artist: "Artist", id: "id-0", added: new Date(2000), cloud: "purchased" },
        {
            name: "Song",
            artist: "Artist",
            id: null,
            added: new Date(1000),
            cloud: "purchased",
            broken: true,
            brokenProp: "id",
        },
    ];
    const playlist = makePlaylist({ name: "MyPlaylist", tracksMeta, failBulk: true });
    const { sandbox, deletions } = buildSandbox([playlist]);

    sandbox.run([]); // apply mode (no --dry-run)

    assert.equal(deletions.length, 0, "no deletions should happen: the only comparable entry has no duplicate");
});

test("fallback: index positions stay correct for real duplicates after a broken track is skipped", () => {
    const tracksMeta = [
        {
            name: "Song",
            artist: "Artist",
            id: null,
            added: new Date(500),
            cloud: "purchased",
            broken: true,
            brokenProp: "id",
        },
        { name: "Other", artist: "Other", id: "id-1", added: new Date(1000), cloud: "purchased" },
        { name: "Other", artist: "Other", id: "id-2", added: new Date(2000), cloud: "purchased" },
    ];
    const playlist = makePlaylist({ name: "MyPlaylist", tracksMeta, failBulk: true });
    const { sandbox, deletions } = buildSandbox([playlist]);

    sandbox.run([]);

    assert.equal(deletions.length, 1);
    assert.equal(
        deletions[0].persistentID(),
        "id-2",
        "later duplicate (idx2) must be the one removed, not shifted by the skipped broken idx0"
    );
});

test("a genuine delete failure causes run() to throw so the process exits nonzero", () => {
    const tracksMeta = [
        { name: "Dup", artist: "Artist", id: "id-0", added: new Date(1000), cloud: "purchased" },
        { name: "Dup", artist: "Artist", id: "id-1", added: new Date(2000), cloud: "purchased" },
    ];
    const playlist = makePlaylist({ name: "MyPlaylist", tracksMeta });
    // idx0 sorts first (earlier) => keeper; idx1 is the loser scheduled for deletion.
    const { sandbox } = buildSandbox([playlist], { deleteShouldFailForIndex: new Set([1]) });

    assert.throws(() => sandbox.run([]));
});

test("a fully-recovered bulk-fetch fallback with zero real errors does not throw", () => {
    const tracksMeta = [
        { name: "A", artist: "Artist", id: "id-0", added: new Date(1000), cloud: "purchased" },
        { name: "B", artist: "Artist", id: "id-1", added: new Date(2000), cloud: "purchased" },
    ];
    const playlist = makePlaylist({ name: "MyPlaylist", tracksMeta, failBulk: true });
    const { sandbox } = buildSandbox([playlist]);

    assert.doesNotThrow(() => sandbox.run([]));
});
