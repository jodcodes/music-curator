/**
 * curator - Browser Frontend
 * Main application logic and state management
 */

// ============================================================================
// Global State
// ============================================================================

const app = {
    config: {
        apiBase: '/api',
        pollInterval: 2000, // ms
        timeout: 30000, // ms
    },
    state: {
        currentView: 'dashboard',
        theme: localStorage.getItem('curator_theme') || 'light',
        isOnline: true,
        playlists: [],
        enrichmentRunning: false,
        enrichmentProgress: 0,
    },
    async api(endpoint, options = {}) {
        const url = `${this.config.apiBase}${endpoint}`;
        const timeout = options.timeout || this.config.timeout;

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), timeout);

            const response = await fetch(url, {
                method: options.method || 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers,
                },
                body: options.body ? JSON.stringify(options.body) : undefined,
                signal: controller.signal,
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            app.state.isOnline = false;
            updateStatus();
            throw error;
        }
    },
};

let curationPreview = null;
let curationPreviewLoading = false;
let curationApplyInFlight = false;
let curationSnapshot = null;
let curationSmokeTest = null;
let curationRefreshLoading = false;
let curationApplyJob = null;
let curationApplyPollTimer = null;
const CURATION_SMALL_APPLY_TRACK_LIMIT = 1;

// ============================================================================
// DOM Elements
// ============================================================================

const DOM = {
    navbar: () => document.querySelector('.navbar'),
    pageTitle: () => document.getElementById('pageTitle'),
    statusIndicator: () => document.getElementById('statusIndicator'),
    alertBanner: () => document.getElementById('alertBanner'),
    views: () => document.querySelectorAll('.view'),
    loadingSpinner: () => document.getElementById('loadingSpinner'),
    navLinks: () => document.querySelectorAll('.nav-link'),
    themeToggle: () => document.getElementById('themeToggle'),
    menuToggle: () => document.getElementById('menuToggle'),
    navMenu: () => document.getElementById('navMenu'),

    // Dashboard
    statPlaylists: () => document.getElementById('statPlaylists'),
    statTracks: () => document.getElementById('statTracks'),
    statClassified: () => document.getElementById('statClassified'),
    statPlatform: () => document.getElementById('statPlatform'),
    recentActivity: () => document.getElementById('recentActivity'),

    // History
    historyRunsBody: () => document.getElementById('historyRunsBody'),
    historyJobsBody: () => document.getElementById('historyJobsBody'),
    historyDedupBody: () => document.getElementById('historyDedupBody'),

    // Playlists
    playlistsBody: () => document.getElementById('playlistsBody'),
    playlistsTable: () => document.getElementById('playlistsTable'),
    playlistSearch: () => document.getElementById('playlistSearch'),
    genreFilter: () => document.getElementById('genreFilter'),

    // Enrichment
    startEnrichmentBtn: () => document.getElementById('startEnrichmentBtn'),
    cancelEnrichmentBtn: () => document.getElementById('cancelEnrichmentBtn'),
    enrichmentProgress: () => document.getElementById('enrichmentProgress'),
    enrichmentProgressBar: () => document.getElementById('enrichmentProgressBar'),
    enrichmentStatus: () => document.getElementById('enrichmentStatus'),
    enrichmentResults: () => document.getElementById('enrichmentResults'),

    // Analysis
    startAnalysisBtn: () => document.getElementById('startAnalysisBtn'),
    analyzePlaylists: () => document.getElementById('analyzePlaylists'),
    analysisResults: () => document.getElementById('analysisResults'),
    moodChart: () => document.getElementById('moodChart'),

    // Organization
    reviewChangesBtn: () => document.getElementById('reviewChangesBtn'),
    platformWarning: () => document.getElementById('platformWarning'),
    organizationPreview: () => document.getElementById('organizationPreview'),
    previewTable: () => document.getElementById('previewTable'),
    previewBody: () => document.getElementById('previewBody'),
    confirmMoveBtn: () => document.getElementById('confirmMoveBtn'),
    cancelMoveBtn: () => document.getElementById('cancelMoveBtn'),

    // Curation
    curationLoadSnapshotBtn: () => document.getElementById('curation-load-snapshot-btn'),
    curationRefreshBtn: () => document.getElementById('curation-refresh-btn'),
    curationDryRunBtn: () => document.getElementById('curation-dry-run-btn'),
    curationSmokeTestBtn: () => document.getElementById('curation-smoke-test-btn'),
    curationApplyBtn: () => document.getElementById('curation-apply-btn'),
    curationSummary: () => document.getElementById('curation-summary'),
    curationGenreTree: () => document.getElementById('curation-genre-tree'),
    curationReviewPanel: () => document.getElementById('curation-review-panel'),
    curationChangePanel: () => document.getElementById('curation-change-panel'),
    curationSystemStatus: () => document.getElementById('curation-system-status'),
    curationGenreFilter: () => document.getElementById('curation-genre-filter'),

    // Modal
    confirmModal: () => document.getElementById('confirmModal'),
    modalBackdrop: () => document.getElementById('modalBackdrop'),
    confirmTitle: () => document.getElementById('confirmTitle'),
    confirmMessage: () => document.getElementById('confirmMessage'),
    confirmYes: () => document.getElementById('confirmYes'),
    confirmNo: () => document.getElementById('confirmNo'),
};

// ============================================================================
// UI Utilities
// ============================================================================

function showAlert(message, type = 'info') {
    const banner = DOM.alertBanner();
    banner.textContent = message;
    banner.className = `alert alert-${type}`;
    setTimeout(() => {
        banner.classList.add('alert-hidden');
    }, 5000);
}

function showSpinner(show = true) {
    const spinner = DOM.loadingSpinner();
    if (show) {
        spinner.classList.remove('hidden');
    } else {
        spinner.classList.add('hidden');
    }
}

function showView(viewName) {
    DOM.views().forEach(view => view.classList.remove('active'));
    const viewIds = {
        curation: 'curation-view',
    };
    const view = document.getElementById(viewIds[viewName] || viewName);
    if (view) {
        view.classList.add('active');
        DOM.navLinks().forEach(link => {
            link.classList.toggle('active', link.dataset.view === viewName);
        });
        app.state.currentView = viewName;
        localStorage.setItem('curator_view', viewName);

        // Update page title
        const titles = {
            dashboard: 'Dashboard',
            playlists: 'Playlists',
            enrich: 'Enrich Metadata',
            analyze: 'Analyze Mood',
            organize: 'Organize Playlists',
            curation: 'Curation Review',
            history: 'Library History',
        };
        DOM.pageTitle().textContent = titles[viewName] || viewName;
    }
}

function showModal(title, message) {
    return new Promise((resolve) => {
        DOM.confirmTitle().textContent = title;
        DOM.confirmMessage().textContent = message;
        DOM.confirmModal().classList.remove('hidden');
        DOM.modalBackdrop().classList.remove('hidden');

        DOM.confirmYes().onclick = () => {
            closeModal();
            resolve(true);
        };

        DOM.confirmNo().onclick = () => {
            closeModal();
            resolve(false);
        };

        DOM.modalBackdrop().onclick = () => {
            closeModal();
            resolve(false);
        };
    });
}

function closeModal() {
    DOM.confirmModal().classList.add('hidden');
    DOM.modalBackdrop().classList.add('hidden');
}

function updateStatus() {
    const indicator = DOM.statusIndicator();
    if (app.state.isOnline) {
        indicator.className = 'status-online';
        indicator.textContent = '● Online';
    } else {
        indicator.className = 'status-offline';
        indicator.textContent = '● Offline';
    }
}

function asArray(value) {
    return Array.isArray(value) ? value : [];
}

function asNumber(value, fallback = 0) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
}

function textValue(value, fallback = '') {
    if (value === null || value === undefined || value === '') {
        return fallback;
    }
    return String(value);
}

function appendElement(parent, tagName, className, text) {
    const element = document.createElement(tagName);
    if (className) {
        element.className = className;
    }
    if (text !== undefined && text !== null) {
        element.textContent = String(text);
    }
    parent.appendChild(element);
    return element;
}

// ============================================================================
// Theme Management
// ============================================================================

function initTheme() {
    const theme = app.state.theme;
    document.documentElement.classList.toggle('dark', theme === 'dark');
    updateThemeToggleButton();
}

function toggleTheme() {
    app.state.theme = app.state.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('curator_theme', app.state.theme);
    document.documentElement.classList.toggle('dark');
    updateThemeToggleButton();
}

function updateThemeToggleButton() {
    const btn = DOM.themeToggle();
    btn.textContent = app.state.theme === 'dark' ? '☀️' : '🌙';
}

// ============================================================================
// Dashboard
// ============================================================================

async function loadDashboard() {
    try {
        showSpinner(true);
        const health = await app.api('/health');

        DOM.statPlaylists().textContent = health.playlists_count || 0;
        DOM.statTracks().textContent = health.tracks_count || 0;
        DOM.statClassified().textContent = health.playlists_count || 0; // TODO: track classified
        DOM.statPlatform().textContent = health.platform.includes('darwin') ? 'macOS' : 'Other';

        app.state.isOnline = true;
        updateStatus();

        // Load recent activity from history
        loadRecentActivity();
    } catch (error) {
        showAlert('Failed to load dashboard: ' + error.message, 'danger');
    } finally {
        showSpinner(false);
    }
}

async function loadRecentActivity() {
    try {
        const data = await app.api('/history?limit=5');
        const el = DOM.recentActivity();
        if (!el) return;

        const runs = asArray(data.runs);
        const jobs = asArray(data.jobs);

        if (!runs.length && !jobs.length) {
            el.innerHTML = '<p class="text-muted">No recent activity</p>';
            return;
        }

        const items = [
            ...runs.map(r => ({
                ts: r.created_at || '',
                label: `${r.run_type} — ${r.status}`,
                sub: r.target ? `Target: ${r.target}` : '',
                icon: r.status === 'completed' ? '✓' : r.status === 'running' ? '⟳' : '✗',
                cls: r.status === 'completed' ? 'success' : r.status === 'running' ? 'info' : 'warning',
            })),
            ...jobs.map(j => ({
                ts: j.created_at || '',
                label: `${j.type} job — ${j.status}`,
                sub: j.progress != null ? `${j.progress}%` : '',
                icon: j.status === 'completed' ? '✓' : j.status === 'running' ? '⟳' : '✗',
                cls: j.status === 'completed' ? 'success' : 'info',
            })),
        ]
        .sort((a, b) => b.ts.localeCompare(a.ts))
        .slice(0, 5);

        el.innerHTML = items.map(item => `
            <div class="activity-item activity-${item.cls}">
                <span class="activity-icon">${item.icon}</span>
                <div>
                    <strong>${item.label}</strong>
                    ${item.sub ? `<small class="text-muted"> — ${item.sub}</small>` : ''}
                    <div class="text-muted" style="font-size:0.75em">${item.ts}</div>
                </div>
            </div>
        `).join('');
    } catch (_) {
        // non-fatal; dashboard still works without history
    }
}

// ============================================================================
// Playlists
// ============================================================================

async function loadPlaylists() {
    try {
        showSpinner(true);
        const playlists = await app.api('/playlists');
        app.state.playlists = playlists;

        renderPlaylistsTable(playlists);
        app.state.isOnline = true;
        updateStatus();
    } catch (error) {
        showAlert('Failed to load playlists: ' + error.message, 'danger');
    } finally {
        showSpinner(false);
    }
}

function renderPlaylistsTable(playlists) {
    const body = DOM.playlistsBody();
    if (!playlists || playlists.length === 0) {
        body.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No playlists found. Open Music.app and allow Automation access for Terminal/Python in macOS Privacy settings.</td></tr>';
        return;
    }

    body.innerHTML = playlists.map(p => `
        <tr>
            <td><strong>${p.name || 'Unnamed'}</strong></td>
            <td>${p.track_count || 0}</td>
            <td>${p.genre ? `<span style="color: var(--color-primary);">${p.genre}</span>` : '-'}</td>
            <td>${p.classified ? '✓ Classified' : '-'}</td>
            <td>
                <div class="table-actions">
                    <button class="btn btn-primary btn-sm" onclick="classifyPlaylist('${p.id}')">Classify</button>
                </div>
            </td>
        </tr>
    `).join('');
}

async function classifyPlaylist(playlistId) {
    try {
        showSpinner(true);
        const result = await app.api(`/playlists/${playlistId}/classify`, { method: 'POST' });

        if (result.success) {
            showAlert(`✓ Classified as ${result.genre}`, 'success');
            loadPlaylists(); // Reload
        } else {
            showAlert('Could not classify this playlist', 'warning');
        }
    } catch (error) {
        showAlert('Classification failed: ' + error.message, 'danger');
    } finally {
        showSpinner(false);
    }
}

// ============================================================================
// Enrichment
// ============================================================================

async function startEnrichment() {
    try {
        showSpinner(true);
        const result = await app.api('/enrichment/start', { method: 'POST' });

        if (result.success) {
            app.state.enrichmentRunning = true;
            DOM.startEnrichmentBtn().style.display = 'none';
            DOM.enrichmentProgress().style.display = 'block';
            showAlert('Enrichment started...', 'info');
            pollEnrichmentProgress();
        }
    } catch (error) {
        showAlert('Failed to start enrichment: ' + error.message, 'danger');
    } finally {
        showSpinner(false);
    }
}

async function pollEnrichmentProgress() {
    if (!app.state.enrichmentRunning) return;

    try {
        const status = await app.api('/enrichment/status');

        if (status.running) {
            app.state.enrichmentProgress = status.progress || 0;
            const progressBar = DOM.enrichmentProgressBar();
            progressBar.style.width = app.state.enrichmentProgress + '%';
            progressBar.textContent = app.state.enrichmentProgress + '%';

            const statusText = status.current_operation || 'Processing...';
            DOM.enrichmentStatus().textContent = statusText;

            setTimeout(pollEnrichmentProgress, app.config.pollInterval);
        } else if (status.progress === 100) {
            // Completed
            app.state.enrichmentRunning = false;
            showAlert('✓ Enrichment completed!', 'success');
            DOM.enrichmentProgress().style.display = 'none';
            loadEnrichmentResults();
        }
    } catch (error) {
        showAlert('Error polling progress: ' + error.message, 'danger');
    }
}

async function cancelEnrichment() {
    try {
        await app.api('/enrichment/cancel', { method: 'POST' });
        app.state.enrichmentRunning = false;
        DOM.enrichmentProgress().style.display = 'none';
        DOM.startEnrichmentBtn().style.display = 'block';
        showAlert('✓ Enrichment cancelled', 'success');
    } catch (error) {
        showAlert('Failed to cancel enrichment: ' + error.message, 'danger');
    }
}

async function loadEnrichmentResults() {
    try {
        const results = await app.api('/enrichment/results');

        if (results.tracks_enriched > 0) {
            DOM.enrichmentResults().style.display = 'block';
            DOM.enrichmentResultsSummary().textContent = 
                `✓ Enriched ${results.tracks_enriched} tracks with ${results.fields_added} fields in ${results.duration_seconds}s`;
        }
    } catch (error) {
        console.error('Failed to load enrichment results:', error);
    }
}

// ============================================================================
// Analysis (Temperament)
// ============================================================================

async function startAnalysis() {
    try {
        const select = DOM.analyzePlaylists();
        const selectedIds = Array.from(select.selectedOptions).map(o => o.value).filter(Boolean);

        if (!selectedIds.length) {
            showAlert('Please select at least one playlist', 'warning');
            return;
        }

        showSpinner(true);
        const result = await app.api('/temperament/classify', {
            method: 'POST',
            body: { playlist_ids: selectedIds },
        });

        if (result.success) {
            showAlert('Analysis started...', 'info');
            setTimeout(loadAnalysisResults, 2000); // Wait for analysis to complete
        }
    } catch (error) {
        showAlert('Failed to start analysis: ' + error.message, 'danger');
    } finally {
        showSpinner(false);
    }
}

async function loadAnalysisResults() {
    try {
        const results = await app.api('/temperament/results');

        if (results.length > 0) {
            DOM.analysisResults().style.display = 'block';
            renderTemperamentChart(results);
        }
    } catch (error) {
        console.error('Failed to load analysis results:', error);
    }
}

function renderTemperamentChart(results) {
    const chart = DOM.moodChart();
    chart.innerHTML = results.map(r => `
        <div class="temperament-item ${r.primary_temperament}">
            <div class="temperament-track-name">${r.track_name}</div>
            <div class="temperament-value">
                ${r.primary_temperament}
                <span class="confidence-badge">${(r.confidence * 100).toFixed(0)}%</span>
            </div>
        </div>
    `).join('');
}

// ============================================================================
// Organization
// ============================================================================

// Keep last organize result so confirmMove can pass real changes to /move
let _lastOrganizeChanges = [];

async function reviewChanges() {
    try {
        showSpinner(true);
        const result = await app.api('/playlists/organize', {
            method: 'POST',
            body: { dry_run: true },
        });

        if (result.changes && result.changes.length > 0) {
            _lastOrganizeChanges = result.changes;
            renderOrganizationPreview(result.changes, result.total_changes);
            DOM.organizationPreview().style.display = 'block';
        } else {
            _lastOrganizeChanges = [];
            showAlert('No playlists to organize', 'info');
        }
    } catch (error) {
        showAlert('Failed to review changes: ' + error.message, 'danger');
    } finally {
        showSpinner(false);
    }
}

function renderOrganizationPreview(changes, total) {
    const body = DOM.previewBody();
    body.innerHTML = changes.map(change => `
        <tr>
            <td>${change.name || change.playlist_id}</td>
            <td>${change.current_location || '/Playlists'}</td>
            <td><strong>${change.proposed_location}</strong></td>
            <td>${change.genre}${change.confidence != null ? ` <small>(${(change.confidence * 100).toFixed(0)}%)</small>` : ''}</td>
        </tr>
    `).join('');

    document.getElementById('previewSummary').textContent = 
        `Ready to move ${total} playlist${total !== 1 ? 's' : ''} to organized folders.`;
}

async function confirmMove() {
    const ok = await showModal(
        'Confirm Playlist Organization',
        'This will move playlists to their genre folders. Continue?'
    );

    if (!ok) return;

    try {
        showSpinner(true);
        const result = await app.api('/playlists/move', {
            method: 'POST',
            body: { confirmed: true, changes: _lastOrganizeChanges },
        });

        if (result.failed > 0) {
            showAlert(`Moved ${result.moved}, ${result.failed} failed (${result.duration_seconds}s)`, 'warning');
        } else {
            showAlert(`✓ Moved ${result.moved} playlists in ${result.duration_seconds}s`, 'success');
        }
        DOM.organizationPreview().style.display = 'none';
        _lastOrganizeChanges = [];
        loadPlaylists();
    } catch (error) {
        showAlert('Failed to move playlists: ' + error.message, 'danger');
    } finally {
        showSpinner(false);
    }
}

// ============================================================================
// Curation Review
// ============================================================================

const CURATION_TEMPERS = ['Woe', 'Frolic', 'Dread', 'Malice'];

function hasFreshCurationSnapshot() {
    return Boolean(curationSnapshot && curationSnapshot.available && curationSnapshot.fresh);
}

function hasPassedSmokeTestForCurrentSnapshot() {
    return Boolean(
        hasFreshCurationSnapshot() &&
        curationSmokeTest &&
        curationSmokeTest.success &&
        curationSmokeTest.smoke_test_token &&
        curationSmokeTest.snapshotCreatedAt === curationSnapshot.created_at
    );
}

function setCurationButtonsState() {
    const isBusy = curationPreviewLoading || curationRefreshLoading || curationApplyInFlight;
    const hasFreshSnapshot = hasFreshCurationSnapshot();
    const loadSnapshotBtn = DOM.curationLoadSnapshotBtn();
    const refreshBtn = DOM.curationRefreshBtn();
    const dryRunBtn = DOM.curationDryRunBtn();
    const smokeTestBtn = DOM.curationSmokeTestBtn();
    const applyBtn = DOM.curationApplyBtn();

    if (loadSnapshotBtn) {
        loadSnapshotBtn.disabled = isBusy;
    }
    if (refreshBtn) {
        refreshBtn.disabled = isBusy;
    }
    if (dryRunBtn) {
        dryRunBtn.disabled = isBusy;
    }
    if (smokeTestBtn) {
        smokeTestBtn.disabled = isBusy || !hasFreshSnapshot;
    }
    if (applyBtn) {
        applyBtn.disabled = isBusy || !hasPassedSmokeTestForCurrentSnapshot();
    }
}

async function loadCurationSnapshot() {
    if (curationPreviewLoading || curationRefreshLoading || curationApplyInFlight) {
        return;
    }

    curationPreviewLoading = true;
    setCurationButtonsState();

    try {
        const snapshot = await app.api('/curation/snapshot?scope=fav_songs');

        curationSnapshot = snapshot;
        curationPreview = snapshot && snapshot.available ? snapshot : null;
        curationSmokeTest = null;
        renderCurationControlCenter(snapshot);
        app.state.isOnline = true;
        updateStatus();
    } catch (error) {
        curationSnapshot = null;
        curationPreview = null;
        renderCurationError('Unable to load curation snapshot.');
        showAlert('Failed to load curation snapshot: ' + error.message, 'danger');
    } finally {
        curationPreviewLoading = false;
        setCurationButtonsState();
    }
}

async function refreshCurationSnapshot() {
    if (curationPreviewLoading || curationRefreshLoading || curationApplyInFlight) {
        return;
    }

    curationRefreshLoading = true;
    setCurationButtonsState();
    showSpinner(true);

    try {
        const snapshot = await app.api('/curation/refresh', {
            method: 'POST',
            body: { scope: 'fav_songs' },
        });

        curationSnapshot = snapshot;
        curationPreview = snapshot;
        curationSmokeTest = null;
        renderCurationControlCenter(snapshot);
        app.state.isOnline = true;
        updateStatus();
    } catch (error) {
        curationSnapshot = null;
        curationPreview = null;
        renderCurationError('Unable to refresh curation snapshot.');
        showAlert('Failed to refresh curation snapshot: ' + error.message, 'danger');
    } finally {
        curationRefreshLoading = false;
        setCurationButtonsState();
        showSpinner(false);
    }
}

async function loadCurationPreview() {
    if (curationPreviewLoading || curationApplyInFlight) {
        return;
    }

    curationPreviewLoading = true;
    setCurationButtonsState();

    try {
        showSpinner(true);
        const preview = await app.api('/curation/preview?scope=fav_songs');

        curationPreview = preview;
        renderCurationPreview(preview);
        app.state.isOnline = true;
        updateStatus();
    } catch (error) {
        curationPreview = null;
        renderCurationError('Unable to load curation preview.');
        showAlert('Failed to load curation preview: ' + error.message, 'danger');
    } finally {
        curationPreviewLoading = false;
        setCurationButtonsState();
        showSpinner(false);
    }
}

function groupCurationAssignments(assignments) {
    const groupsByGenre = new Map();

    assignments.forEach(assignment => {
        if (!assignment || typeof assignment !== 'object') {
            return;
        }

        const genre = textValue(assignment.genre_label || assignment.genre, 'Other');
        if (!groupsByGenre.has(genre)) {
            groupsByGenre.set(genre, []);
        }
        groupsByGenre.get(genre).push(assignment);
    });

    return Array.from(groupsByGenre.entries())
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([genre, items], index) => ({
            genre,
            id: `curation-genre-${index}`,
            items: items.slice().sort((left, right) => {
                const leftName = textValue((left && left.item_name) || (left && left.name), 'Unnamed');
                const rightName = textValue((right && right.item_name) || (right && right.name), 'Unnamed');
                return leftName.localeCompare(rightName);
            }),
        }));
}

function renderCurationPreview(preview) {
    const summary = DOM.curationSummary();
    const tree = DOM.curationGenreTree();
    const reviewPanel = DOM.curationReviewPanel();
    const changePanel = DOM.curationChangePanel();

    if (!summary || !tree || !reviewPanel || !changePanel) {
        return;
    }

    const assignments = asArray(preview && preview.assignments);
    const changes = asArray(preview && preview.changes);
    const skippedTracks = asArray(preview && preview.skipped_tracks);
    const groups = groupCurationAssignments(assignments);
    const totalAssignments = asNumber(
        preview && preview.total_assignments !== undefined
            ? preview.total_assignments
            : assignments.length
    );
    const totalChanges = asNumber(
        preview && preview.total_changes !== undefined
            ? preview.total_changes
            : changes.length
    );
    const totalSkipped = asNumber(
        preview && preview.total_skipped !== undefined
            ? preview.total_skipped
            : skippedTracks.length
    );

    renderCurationSummary(summary, {
        totalAssignments,
        totalGenres: groups.length,
        totalChanges,
        totalSkipped,
    });
    renderCurationGenreTree(tree, groups);
    renderCurationReviewPanel(reviewPanel, groups);
    renderCurationChangePanel(changePanel, changes, skippedTracks, totalSkipped);
}

function groupedToMatrixRows(grouped) {
    return Object.entries(grouped || {})
        .map(([genre, temperMap]) => {
            const counts = {};
            CURATION_TEMPERS.forEach(temper => {
                counts[temper] = asArray(temperMap && temperMap[temper]).length;
            });
            const total = Object.values(counts).reduce((sum, value) => sum + value, 0);
            return { genre, counts, total, status: total > 0 ? 'ready' : 'empty' };
        })
        .sort((left, right) => right.total - left.total || left.genre.localeCompare(right.genre));
}

function renderCurationControlCenter(snapshot) {
    const summary = DOM.curationSummary();
    const reviewPanel = DOM.curationReviewPanel();
    const changePanel = DOM.curationChangePanel();

    if (!summary || !reviewPanel || !changePanel) {
        return;
    }

    const grouped = snapshot && snapshot.grouped;
    const rows = groupedToMatrixRows(grouped);
    const changes = asArray(snapshot && snapshot.changes);
    const skippedTracks = asArray(snapshot && snapshot.skipped_tracks);
    const totalAssignments = asNumber(
        snapshot && snapshot.total_assignments !== undefined
            ? snapshot.total_assignments
            : rows.reduce((sum, row) => sum + row.total, 0)
    );
    const totalGenres = asNumber(
        snapshot && snapshot.total_genres !== undefined
            ? snapshot.total_genres
            : rows.length
    );
    const totalChanges = asNumber(
        snapshot && snapshot.total_changes !== undefined
            ? snapshot.total_changes
            : changes.length
    );
    const totalSkipped = asNumber(
        snapshot && snapshot.total_skipped !== undefined
            ? snapshot.total_skipped
            : skippedTracks.length
    );

    renderCurationSystemStatus(snapshot);
    renderCurationSummary(summary, {
        totalAssignments,
        totalGenres,
        totalChanges,
        totalSkipped,
    });
    renderCurationMatrix(reviewPanel, grouped);
    renderCurationWritePanel(snapshot, curationSmokeTest);
}

function renderCurationSystemStatus(snapshot) {
    const status = DOM.curationSystemStatus();
    if (!status) {
        return;
    }

    const snapshotStatus = !snapshot || !snapshot.available
        ? 'Not loaded'
        : snapshot.fresh
            ? 'Fresh'
            : 'Stale';
    const createdAt = snapshot && snapshot.created_at
        ? new Date(snapshot.created_at).toLocaleString()
        : '';

    status.replaceChildren();
    [
        ['SSD', 'Unknown'],
        ['Music.app', 'Unknown'],
        ['Snapshot', createdAt ? `${snapshotStatus} (${createdAt})` : snapshotStatus],
    ].forEach(([label, value]) => {
        const row = appendElement(status, 'div');
        appendElement(row, 'span', null, label);
        appendElement(row, 'strong', null, value);
    });
}

function renderCurationApplyJobStatus(panel) {
    if (!panel || !curationApplyJob) {
        return;
    }

    const status = textValue(curationApplyJob.status, 'queued');
    const progress = asNumber(curationApplyJob.progress, 0);
    const currentTrack = asNumber(curationApplyJob.current_track, 0);
    const totalTracks = asNumber(curationApplyJob.total_tracks, 0);
    const errorMessage = textValue(curationApplyJob.error_message);
    const isFailed = status === 'failed';
    const isCompleted = status === 'completed';
    const statusClass = isFailed ? 'status-danger' : isCompleted ? 'status-success' : 'text-muted';

    appendElement(panel, 'h3', null, 'Apply Job');
    appendElement(panel, 'p', statusClass, `Status: ${status}${progress ? ` (${progress}%)` : ''}`);
    if (currentTrack || totalTracks) {
        appendElement(panel, 'p', 'text-muted', `Tracks: ${currentTrack}/${totalTracks}`);
    }
    appendElement(panel, 'p', 'text-muted', `Job: ${textValue(curationApplyJob.id, 'pending')}`);
    if (errorMessage) {
        appendElement(panel, 'p', 'status-danger', errorMessage);
    }
}

function renderCurationMatrix(panel, grouped) {
    if (!panel) {
        return;
    }

    panel.replaceChildren();

    const allRows = groupedToMatrixRows(grouped);
    const genreFilter = DOM.curationGenreFilter();
    const filterText = genreFilter ? genreFilter.value.trim().toLowerCase() : '';
    const rows = filterText
        ? allRows.filter(row => row.genre.toLowerCase().includes(filterText))
        : allRows;

    if (!allRows.length) {
        const empty = appendElement(panel, 'div', 'card curation-empty-state');
        appendElement(empty, 'h3', null, 'No Snapshot Data');
        appendElement(empty, 'p', 'text-muted', 'Load or refresh a snapshot to review genre and temper counts.');
        return;
    }

    if (!rows.length) {
        const empty = appendElement(panel, 'div', 'card curation-empty-state');
        appendElement(empty, 'h3', null, 'No Matching Genres');
        appendElement(empty, 'p', 'text-muted', 'No snapshot genres match the current filter.');
        return;
    }

    const matrix = appendElement(panel, 'div', 'curation-matrix');
    const header = appendElement(matrix, 'div', 'curation-matrix-row curation-matrix-header');
    ['Genre', ...CURATION_TEMPERS, 'Total / Status'].forEach(label => {
        appendElement(header, 'div', null, label);
    });

    rows.forEach(row => {
        const rowEl = appendElement(matrix, 'div', 'curation-matrix-row');
        appendElement(rowEl, 'div', null, row.genre);
        CURATION_TEMPERS.forEach(temper => {
            appendElement(rowEl, 'div', null, row.counts[temper]);
        });
        appendElement(rowEl, 'div', null, `${row.total} ${row.status}`);
    });
}

function renderCurationWritePanel(snapshot, smokeTest = curationSmokeTest) {
    const panel = DOM.curationChangePanel();
    if (!panel) {
        return;
    }

    const changes = asArray(snapshot && snapshot.changes);
    const skippedTracks = asArray(snapshot && snapshot.skipped_tracks);
    const totalSkipped = asNumber(
        snapshot && snapshot.total_skipped !== undefined
            ? snapshot.total_skipped
            : skippedTracks.length
    );

    panel.replaceChildren();
    appendElement(panel, 'h3', null, 'Write Safety');

    if (!snapshot || !snapshot.available) {
        appendElement(panel, 'p', 'text-muted', 'Snapshot: missing. Refresh before mini-test or apply.');
        appendElement(panel, 'p', 'text-muted', 'Mini-test: not run.');
        return;
    }

    if (!snapshot.fresh) {
        appendElement(panel, 'p', 'text-muted', 'Snapshot: stale. Refresh before mini-test or apply.');
    } else {
        appendElement(panel, 'p', 'text-muted', 'Snapshot: fresh.');
    }

    if (!smokeTest) {
        appendElement(panel, 'p', 'text-muted', 'Mini-test: not run. Apply is locked.');
    } else if (smokeTest.success && hasPassedSmokeTestForCurrentSnapshot()) {
        appendElement(panel, 'p', 'status-success', 'Mini-test: passed. 1-track apply can be queued.');
    } else if (smokeTest.success) {
        appendElement(panel, 'p', 'text-muted', 'Mini-test: not run for the current snapshot. Apply is locked.');
    } else {
        const error = textValue(smokeTest.error, 'Unknown error');
        appendElement(panel, 'p', 'status-danger', `Mini-test: failed. ${error}`);
    }

    renderCurationApplyJobStatus(panel);
    renderCurationChangePanel(panel, changes, skippedTracks, totalSkipped, true);
}

function renderCurationSummary(summary, counts) {
    summary.replaceChildren();

    [
        ['Assignments', counts.totalAssignments],
        ['Genres', counts.totalGenres],
        ['Dry-run Changes', counts.totalChanges],
        ['Skipped', counts.totalSkipped],
    ].forEach(([label, value]) => {
        const item = appendElement(summary, 'div', 'curation-summary-item');
        appendElement(item, 'div', 'curation-summary-number', value);
        appendElement(item, 'div', 'curation-summary-label', label);
    });
}

function renderCurationGenreTree(tree, groups) {
    tree.replaceChildren();
    appendElement(tree, 'h3', null, 'Genres');

    if (!groups.length) {
        appendElement(tree, 'p', 'text-muted', 'No genres found in this preview.');
        return;
    }

    const list = appendElement(tree, 'div', 'curation-genre-list');
    groups.forEach(group => {
        const button = appendElement(list, 'button', 'curation-genre-link');
        button.type = 'button';
        const label = appendElement(button, 'span', null, group.genre);
        label.title = group.genre;
        appendElement(button, 'span', 'curation-count-badge', group.items.length);
        button.addEventListener('click', () => {
            const target = document.getElementById(group.id);
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });
}

function renderCurationReviewPanel(panel, groups) {
    panel.replaceChildren();

    if (!groups.length) {
        const empty = appendElement(panel, 'div', 'card curation-empty-state');
        appendElement(empty, 'h3', null, 'No Favourite Songs Found');
        appendElement(empty, 'p', 'text-muted', 'The preview returned no curation assignments.');
        return;
    }

    groups.forEach(group => {
        const section = appendElement(panel, 'section', 'card curation-genre-section');
        section.id = group.id;
        const header = appendElement(section, 'div', 'curation-genre-header');
        appendElement(header, 'h3', null, group.genre);
        appendElement(header, 'span', 'curation-count-badge', group.items.length);

        const grid = appendElement(section, 'div', 'curation-temper-grid');
        CURATION_TEMPERS.forEach(temper => {
            const column = appendElement(grid, 'div', 'curation-temper-column');
            const columnHeader = appendElement(column, 'div', 'curation-temper-header');
            const temperItems = group.items.filter(item => textValue(item && item.temperament) === temper);

            appendElement(columnHeader, 'h4', null, temper);
            appendElement(columnHeader, 'span', 'curation-count-badge', temperItems.length);

            if (!temperItems.length) {
                appendElement(column, 'p', 'curation-empty-column', 'No tracks');
                return;
            }

            temperItems.forEach(item => {
                const card = appendElement(column, 'div', 'curation-track-card');
                const itemName = textValue((item && item.item_name) || (item && item.name), 'Unnamed track');
                const targetPath = asArray(item && item.target_path).map(part => textValue(part)).join(' / ');

                appendElement(card, 'div', 'curation-track-name', itemName);
                appendElement(card, 'div', 'curation-target-path', targetPath || 'No target path');
            });
        });
    });
}

function renderCurationChangePanel(panel, changes, skippedTracks, totalSkipped, preserveExisting = false) {
    if (!preserveExisting) {
        panel.replaceChildren();
    }
    appendElement(panel, 'h3', null, 'Dry-run Changes');

    if (!changes.length) {
        appendElement(panel, 'p', 'text-muted', 'No dry-run changes returned.');
    } else {
        const list = appendElement(panel, 'div', 'curation-change-list');
        changes.forEach(change => {
            const item = appendElement(list, 'div', 'curation-change-item');
            const action = textValue(change && change.action, 'change');
            const description = textValue(change && change.description, 'Change planned');
            const path = asArray(change && change.path).map(part => textValue(part)).join(' / ');

            appendElement(item, 'span', 'curation-action-badge', action.replace(/_/g, ' '));
            appendElement(item, 'div', 'curation-change-description', description);
            if (path) {
                appendElement(item, 'div', 'curation-target-path', path);
            }
        });
    }

    if (totalSkipped > 0 || skippedTracks.length > 0) {
        const skipped = appendElement(panel, 'div', 'curation-skipped-section');
        appendElement(skipped, 'h3', null, `Skipped Tracks (${totalSkipped || skippedTracks.length})`);

        if (!skippedTracks.length) {
            appendElement(skipped, 'p', 'text-muted', 'Skipped track details were not returned.');
            return;
        }

        skippedTracks.forEach(track => {
            const row = appendElement(skipped, 'div', 'curation-skipped-item');
            const name = textValue((track && track.name) || (track && track.item_name), 'Unnamed track');
            const details = [
                textValue(track && track.artist),
                textValue(track && track.genre),
                textValue(track && track.reason, 'skipped'),
            ].filter(Boolean).join(' - ');

            appendElement(row, 'div', 'curation-track-name', name);
            appendElement(row, 'div', 'curation-target-path', details);
        });
    }
}

function renderCurationError(message) {
    const summary = DOM.curationSummary();
    const tree = DOM.curationGenreTree();
    const reviewPanel = DOM.curationReviewPanel();
    const changePanel = DOM.curationChangePanel();

    if (!summary || !reviewPanel || !changePanel) {
        return;
    }

    renderCurationSystemStatus(null);
    renderCurationSummary(summary, {
        totalAssignments: 0,
        totalGenres: 0,
        totalChanges: 0,
        totalSkipped: 0,
    });

    if (tree) {
        tree.replaceChildren();
        appendElement(tree, 'h3', null, 'Genres');
        appendElement(tree, 'p', 'text-muted', 'No preview loaded.');
    }

    reviewPanel.replaceChildren();
    const empty = appendElement(reviewPanel, 'div', 'card curation-empty-state');
    appendElement(empty, 'h3', null, 'Snapshot Unavailable');
    appendElement(empty, 'p', 'text-muted', message);

    changePanel.replaceChildren();
    appendElement(changePanel, 'h3', null, 'Write Safety');
    appendElement(changePanel, 'p', 'text-muted', 'No changes loaded.');
}

async function runCurationSmokeTest() {
    if (!hasFreshCurationSnapshot()) {
        showAlert('Refresh the curation snapshot before running the mini-test.', 'warning');
        return;
    }

    curationApplyInFlight = true;
    setCurationButtonsState();

    try {
        const result = await app.api('/curation/smoke-test', {
            method: 'POST',
            body: { scope: 'fav_songs' },
        });

        curationSmokeTest = { ...result, snapshotCreatedAt: curationSnapshot.created_at };
        renderCurationWritePanel(curationSnapshot, curationSmokeTest);
        showAlert('Mini-test completed and cleaned up.', 'success');
    } catch (error) {
        curationSmokeTest = { success: false, error: error.message };
        renderCurationWritePanel(curationSnapshot, curationSmokeTest);
        showAlert('Mini-test failed: ' + error.message, 'danger');
    } finally {
        curationApplyInFlight = false;
        setCurationButtonsState();
    }
}

function clearCurationApplyPollTimer() {
    if (curationApplyPollTimer) {
        clearTimeout(curationApplyPollTimer);
        curationApplyPollTimer = null;
    }
}

function isTerminalCurationJobStatus(status) {
    return ['completed', 'failed', 'cancelled', 'timeout'].includes(status);
}

async function pollCurationApplyJob(jobId) {
    clearCurationApplyPollTimer();

    try {
        const job = await app.api(`/jobs/${encodeURIComponent(jobId)}`);
        curationApplyJob = job;
        renderCurationWritePanel(curationSnapshot, curationSmokeTest);

        if (isTerminalCurationJobStatus(job.status)) {
            curationApplyInFlight = false;
            setCurationButtonsState();
            if (job.status === 'completed') {
                showAlert('1-track apply completed.', 'success');
                await loadCurationSnapshot();
            } else {
                showAlert(`Apply job ${job.status}: ${textValue(job.error_message, job.id)}`, 'danger');
            }
            return;
        }

        curationApplyPollTimer = setTimeout(
            () => pollCurationApplyJob(jobId),
            app.config.pollInterval
        );
    } catch (error) {
        curationApplyInFlight = false;
        setCurationButtonsState();
        showAlert('Failed to poll apply job: ' + error.message, 'danger');
    }
}

async function applyFavSongsCuration() {
    if (curationApplyInFlight || curationPreviewLoading || curationRefreshLoading) {
        return;
    }

    if (!hasPassedSmokeTestForCurrentSnapshot()) {
        setCurationButtonsState();
        showAlert('Run a successful mini-test against the current fresh snapshot before apply.', 'warning');
        return;
    }

    if (!curationPreview) {
        setCurationButtonsState();
        showAlert('Load a successful curation preview before applying changes.', 'warning');
        return;
    }

    const confirmed = window.confirm(
        `Queue a ${CURATION_SMALL_APPLY_TRACK_LIMIT}-track Favourite Songs apply test in Apple Music? This can create folders, playlists, and copy one track.`
    );

    if (!confirmed) {
        return;
    }

    curationApplyInFlight = true;
    setCurationButtonsState();

    try {
        showSpinner(true);
        const result = await app.api('/curation/apply', {
            method: 'POST',
            body: {
                scope: 'fav_songs',
                confirmed: true,
                mini_test_passed: hasPassedSmokeTestForCurrentSnapshot(),
                smoke_test_token: curationSmokeTest.smoke_test_token,
                max_tracks: CURATION_SMALL_APPLY_TRACK_LIMIT,
            },
        });

        curationApplyJob = {
            id: result.job_id,
            status: result.status || 'queued',
            progress: 0,
        };
        renderCurationWritePanel(curationSnapshot, curationSmokeTest);
        showAlert(`1-track apply queued: ${result.job_id}`, 'success');
        setCurationButtonsState();
        pollCurationApplyJob(result.job_id);
    } catch (error) {
        clearCurationApplyPollTimer();
        curationApplyInFlight = false;
        showAlert('Failed to apply curation: ' + error.message, 'danger');
    } finally {
        setCurationButtonsState();
        showSpinner(false);
    }
}

// ============================================================================
// History
// ============================================================================

async function loadHistory() {
    try {
        showSpinner(true);
        const [histData, dedupData] = await Promise.all([
            app.api('/history?limit=50'),
            app.api('/dedupe?limit=50'),
        ]);

        // Runs table
        const runsBody = DOM.historyRunsBody();
        if (runsBody) {
            const runs = asArray(histData.runs);
            if (runs.length) {
                runsBody.innerHTML = runs.map(r => `
                    <tr>
                        <td><code>${r.id}</code></td>
                        <td>${r.run_type}</td>
                        <td>${r.target || '—'}</td>
                        <td><span class="badge badge-${r.status === 'completed' ? 'success' : r.status === 'running' ? 'info' : 'warning'}">${r.status}</span></td>
                        <td>${r.processed_items || 0}</td>
                        <td>${r.skipped_items || 0}</td>
                        <td>${r.started_at ? r.started_at.replace('T', ' ').slice(0, 19) : '—'}</td>
                    </tr>
                `).join('');
            } else {
                runsBody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No runs yet</td></tr>';
            }
        }

        // Jobs table
        const jobsBody = DOM.historyJobsBody();
        if (jobsBody) {
            const jobs = asArray(histData.jobs);
            if (jobs.length) {
                jobsBody.innerHTML = jobs.map(j => `
                    <tr>
                        <td><code>${j.id}</code></td>
                        <td>${j.type}</td>
                        <td>${j.status}</td>
                        <td>${j.progress != null ? j.progress + '%' : '—'}</td>
                        <td>${j.created_at ? j.created_at.replace('T', ' ').slice(0, 19) : '—'}</td>
                    </tr>
                `).join('');
            } else {
                jobsBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No jobs yet</td></tr>';
            }
        }

        // Dedup table
        const dedupBody = DOM.historyDedupBody();
        if (dedupBody) {
            const entries = asArray(dedupData.entries);
            if (entries.length) {
                dedupBody.innerHTML = entries.map(e => `
                    <tr>
                        <td>${e.artist || '—'}</td>
                        <td>${e.title || '—'}</td>
                        <td>${e.album || '—'}</td>
                        <td><code>${e.scope || '—'}</code></td>
                        <td>${e.skip_reason || '—'}</td>
                        <td>${e.last_seen_at ? e.last_seen_at.replace('T', ' ').slice(0, 19) : '—'}</td>
                    </tr>
                `).join('');
            } else {
                dedupBody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No dedup entries yet</td></tr>';
            }
        }

        app.state.isOnline = true;
        updateStatus();
    } catch (error) {
        showAlert('Failed to load history: ' + error.message, 'danger');
    } finally {
        showSpinner(false);
    }
}

// ============================================================================
// Event Listeners
// ============================================================================

function setupEventListeners() {
    // Navigation
    DOM.navLinks().forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const view = link.dataset.view;
            showView(view);

            // Load view-specific data
            if (view === 'playlists') loadPlaylists();
            if (view === 'dashboard') loadDashboard();
            if (view === 'curation') loadCurationSnapshot();
            if (view === 'history') loadHistory();
        });
    });

    // Mobile menu
    DOM.menuToggle().addEventListener('click', () => {
        DOM.navMenu().classList.toggle('show');
    });

    // Theme toggle
    DOM.themeToggle().addEventListener('click', toggleTheme);

    // Dashboard actions
    document.querySelectorAll('[data-action]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const action = btn.dataset.action;
            const views = { classify: 'playlists', enrich: 'enrich', analyze: 'analyze', organize: 'organize' };
            if (views[action]) showView(views[action]);
        });
    });

    // Enrichment
    DOM.startEnrichmentBtn().addEventListener('click', startEnrichment);
    DOM.cancelEnrichmentBtn().addEventListener('click', cancelEnrichment);

    // Analysis
    DOM.startAnalysisBtn().addEventListener('click', startAnalysis);

    // Organization
    DOM.reviewChangesBtn().addEventListener('click', reviewChanges);
    DOM.confirmMoveBtn().addEventListener('click', confirmMove);
    DOM.cancelMoveBtn().addEventListener('click', () => {
        DOM.organizationPreview().style.display = 'none';
    });

    // Curation
    if (DOM.curationLoadSnapshotBtn()) {
        DOM.curationLoadSnapshotBtn().addEventListener('click', loadCurationSnapshot);
    }
    if (DOM.curationRefreshBtn()) {
        DOM.curationRefreshBtn().addEventListener('click', refreshCurationSnapshot);
    }
    if (DOM.curationDryRunBtn()) {
        DOM.curationDryRunBtn().addEventListener('click', loadCurationPreview);
    }
    if (DOM.curationSmokeTestBtn()) {
        DOM.curationSmokeTestBtn().addEventListener('click', runCurationSmokeTest);
    }
    if (DOM.curationGenreFilter()) {
        DOM.curationGenreFilter().addEventListener('input', () => {
            renderCurationMatrix(DOM.curationReviewPanel(), curationSnapshot && curationSnapshot.grouped);
        });
    }
    if (DOM.curationApplyBtn()) {
        DOM.curationApplyBtn().addEventListener('click', applyFavSongsCuration);
    }
    setCurationButtonsState();
}

// ============================================================================
// Initialization
// ============================================================================

async function init() {
    try {
        // Setup theme
        initTheme();

        // Setup event listeners
        setupEventListeners();

        // Load initial data
        await app.api('/config');
        app.state.isOnline = true;
        updateStatus();

        // Load dashboard
        loadDashboard();

        // Restore last view
        const lastView = localStorage.getItem('curator_view') || 'dashboard';
        showView(lastView);
        if (lastView === 'curation') {
            loadCurationSnapshot();
        }
        if (lastView === 'history') {
            loadHistory();
        }
    } catch (error) {
        showAlert('Failed to initialize application: ' + error.message, 'danger');
        app.state.isOnline = false;
        updateStatus();
    }
}

// Start application when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
