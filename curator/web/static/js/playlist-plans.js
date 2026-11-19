(() => {
    const element = id => document.getElementById(id);
    const kind = element('planKind');
    const source = element('planSource');
    const sources = element('planSources');
    const seed = element('planSeed');
    const limit = element('planLimit');
    const previewButton = element('planPreviewButton');
    const applyButton = element('planApplyButton');
    const confirmed = element('planConfirmed');
    const status = element('planStatus');
    let reviewed = null;
    let busy = false;
    let trackGeneration = 0;
    let expiryTimer;

    function invalidate(message = 'Selection changed. Preview again.') {
        reviewed = null;
        clearTimeout(expiryTimer);
        confirmed.checked = false;
        element('planReview').hidden = true;
        status.textContent = message;
        refresh();
    }

    function refresh() {
        const isSeed = kind.value === 'seed';
        element('planSeedFields').hidden = !isSeed;
        element('planSplitFields').hidden = isSeed;
        element('planSeedFields').disabled = busy || !isSeed;
        element('planSplitFields').disabled = busy || isSeed;
        kind.disabled = busy;
        element('planLoadSources').disabled = busy;
        const ready = isSeed
            ? source.value && seed.value && limit.checkValidity()
            : sources.selectedOptions.length > 0;
        previewButton.disabled = busy || !ready;
        confirmed.disabled = busy || !reviewed;
        applyButton.disabled = busy || !reviewed || !confirmed.checked;
    }

    function fill(select, rows, label) {
        select.replaceChildren(new Option('Choose…', ''));
        for (const row of rows) {
            select.add(new Option(label(row), row.persistent_id));
        }
        select.disabled = rows.length === 0;
    }

    element('planLoadSources').addEventListener('click', async () => {
        busy = true;
        ++trackGeneration;
        invalidate('Reading source playlists…');
        seed.replaceChildren();
        seed.disabled = true;
        source.replaceChildren();
        sources.replaceChildren();
        try {
            const rows = await app.api('/playlist-plans/sources');
            const label = row => `${row.name} — ${row.track_count} tracks [${row.persistent_id}]`;
            fill(source, rows, label);
            fill(sources, rows, label);
            sources.options[0].remove();
            status.textContent = rows.length ? 'Choose source playlists.' : 'No eligible source playlists.';
        } catch (error) {
            status.textContent = `Unable to load sources: ${error.message}`;
        } finally {
            busy = false;
            refresh();
        }
    });

    source.addEventListener('change', async () => {
        const generation = ++trackGeneration;
        invalidate('Reading seed tracks…');
        seed.replaceChildren();
        seed.disabled = true;
        refresh();
        if (!source.value) {
            status.textContent = 'Choose a source playlist.';
            return;
        }
        try {
            const rows = await app.api(`/playlist-plans/source/${encodeURIComponent(source.value)}/tracks`);
            if (generation !== trackGeneration) return;
            fill(seed, rows, row => `${row.name || row.title || 'Untitled'} — ${row.artist || 'Unknown artist'} [${row.persistent_id}]`);
            status.textContent = rows.length ? 'Choose an explicit seed track.' : 'Source has no eligible tracks.';
        } catch (error) {
            if (generation === trackGeneration) status.textContent = `Unable to read tracks: ${error.message}`;
        } finally {
            if (generation === trackGeneration) refresh();
        }
    });

    for (const input of [kind, sources, seed, limit]) {
        input.addEventListener(input === limit ? 'input' : 'change', () => {
            if (input === kind) ++trackGeneration;
            invalidate();
        });
    }
    confirmed.addEventListener('change', refresh);

    previewButton.addEventListener('click', async () => {
        if (previewButton.disabled) return;
        ++trackGeneration;
        const selectedKind = kind.value;
        const body = selectedKind === 'seed'
            ? { playlist_id: source.value, seed_track_id: seed.value, limit: Number(limit.value) }
            : { playlist_ids: Array.from(sources.selectedOptions, option => option.value) };
        busy = true;
        invalidate('Reading exact preview; no playlists are changed…');
        element('planResult').hidden = true;
        try {
            const response = await app.api(`/playlist-plans/${selectedKind}/preview`, { method: 'POST', body });
            reviewed = { kind: selectedKind, id: response.plan_id };
            element('planDetails').textContent = JSON.stringify(response.plan, null, 2);
            element('planReview').hidden = false;
            status.textContent = 'Read-only preview ready. Review the exact plan before confirming.';
            expiryTimer = setTimeout(() => invalidate('Plan expired. Preview again.'), response.expires_in * 1000);
        } catch (error) {
            status.textContent = `Preview failed: ${error.message}`;
        } finally {
            busy = false;
            refresh();
        }
    });

    applyButton.addEventListener('click', async () => {
        if (applyButton.disabled || !reviewed || !confirmed.checked) return;
        ++trackGeneration;
        const plan = reviewed;
        busy = true;
        invalidate('Submitting once. Do not retry if the outcome is uncertain.');
        element('planResult').hidden = true;
        try {
            const report = await app.api(`/playlist-plans/${plan.kind}/apply`, {
                method: 'POST', body: { plan_id: plan.id, confirmed: true },
            });
            element('planReport').textContent = JSON.stringify(report, null, 2);
            status.textContent = report.success === true ? 'Apply completed. See report.' : 'Apply did not complete. Inspect report; do not retry uncertain writes.';
        } catch (error) {
            element('planReport').textContent = JSON.stringify(error.report || {
                success: false, error: error.message,
                outcome: 'Unknown. Inspect journal and Music manually; do not resubmit.',
            }, null, 2);
            status.textContent = 'Apply failed or is uncertain. See report; no automatic retry.';
        } finally {
            element('planResult').hidden = false;
            busy = false;
            refresh();
        }
    });
    refresh();
})();
