// Contract test for sort_favourites_by_genre.js: real per-track add errors
// must never be swallowed into a "successful" exit.
//
// Run: node --test music_tools/tests/test_sort_favourites_by_genre.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCRIPT_PATH = path.join(__dirname, "..", "scripts", "sort_favourites_by_genre.js");
const SCRIPT_SOURCE = fs.readFileSync(SCRIPT_PATH, "utf8");

function makeBulkTrackList(tracksMeta) {
    return {
        persistentID: () => tracksMeta.map((t) => t.id),
        name: () => tracksMeta.map((t) => t.name),
        artist: () => tracksMeta.map((t) => t.artist),
        genre: () => tracksMeta.map((t) => t.genre),
        get length() {
            return tracksMeta.length;
        },
    };
}

function buildSandbox({ favTracks, addShouldFail = false }) {
    const shellLog = [];
    const created = new Map(); // name -> playlist fake
    const duplicateCalls = [];
    const addCalls = [];

    function makePlaylistFake(name) {
        const meta = [];
        return {
            name,
            _meta: meta,
            tracks: makeBulkTrackList(meta),
        };
    }

    const emptyPlaylistsWhose = { length: 0 };

    const favTrackList = {
        length: favTracks.length,
    };
    favTracks.forEach((t, i) => {
        favTrackList[i] = {
            name: () => t.name,
            artist: () => t.artist,
            genre: () => t.genre,
            persistentID: () => t.id,
        };
    });

    const Music = {
        includeStandardAdditions: false,
        timeout: 60,
        userPlaylists: Object.assign(
            () => [...created.values()].map((p) => ({ name: () => p.name, tracks: p.tracks })),
            { whose: ({ name }) => (created.has(name) ? [created.get(name)] : []) }
        ),
        UserPlaylist: (spec) => ({
            make: () => {
                const p = makePlaylistFake(spec.name);
                created.set(spec.name, p);
                return { name: () => p.name, tracks: p.tracks, _meta: p._meta };
            },
        }),
        playlists: {
            whose: ({ name }) => (name === "Favourite Songs" ? [{ tracks: favTrackList }] : []),
        },
        duplicate: (t, { to }) => {
            duplicateCalls.push(t);
            if (addShouldFail) throw new Error("duplicate failed");
            to._meta.push({ id: t.persistentID(), name: t.name(), artist: t.artist(), genre: t.genre() });
        },
        add: (arr, { to }) => {
            addCalls.push(arr);
            if (addShouldFail) throw new Error("add failed too");
            to._meta.push({ id: arr[0].persistentID(), name: arr[0].name(), artist: arr[0].artist(), genre: arr[0].genre() });
        },
        delete: () => {},
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
    vm.runInContext(SCRIPT_SOURCE, sandbox, { filename: "sort_favourites_by_genre.js" });
    return { sandbox };
}

test("a real per-track add failure causes run() to throw so the process exits nonzero", () => {
    const { sandbox } = buildSandbox({
        favTracks: [{ id: "id-1", name: "Song", artist: "Artist", genre: "House" }],
        addShouldFail: true,
    });

    assert.throws(() => sandbox.run());
});

test("a fully successful run does not throw", () => {
    const { sandbox } = buildSandbox({
        favTracks: [{ id: "id-1", name: "Song", artist: "Artist", genre: "House" }],
        addShouldFail: false,
    });

    assert.doesNotThrow(() => sandbox.run());
});
