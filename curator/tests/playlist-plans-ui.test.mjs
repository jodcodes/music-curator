import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const { default: puppeteer } = await import(process.env.PUPPETEER_MODULE || 'puppeteer');
const PID = '0123456789ABCDEF';
const TID = 'FEDCBA9876543210';
const TOKEN = 'fixture-only-access-token-0123456789abcdef';
const directory = await mkdtemp(join(tmpdir(), 'curator-ui-fixtures-'));
let browser;
let server;

async function bounded(operation, milliseconds = 5000) {
    let timer;
    try {
        return await Promise.race([operation, new Promise((_, reject) => {
            timer = setTimeout(() => reject(new Error('Fixture deadline exceeded')), milliseconds);
        })]);
    } finally {
        clearTimeout(timer);
    }
}

try {
    server = spawn(process.env.CURATOR_TEST_PYTHON || 'python3', [
        '-B', fileURLToPath(new URL('./fixtures/playlist_plan_server.py', import.meta.url)),
    ], { env: { ...process.env, CURATOR_FIXTURE_DIR: directory }, stdio: ['ignore', 'pipe', 'pipe'] });
    let diagnostics = '';
    server.stderr.on('data', chunk => { diagnostics += chunk; });
    const origin = await bounded(new Promise((resolve, reject) => {
        let output = '';
        server.on('error', reject);
        server.on('exit', code => reject(new Error(`Fixture server exited ${code}: ${diagnostics}`)));
        server.stdout.on('data', chunk => {
            output += chunk;
            for (const line of output.split('\n')) {
                if (line.startsWith('{')) {
                    try { resolve(JSON.parse(line).origin); } catch {}
                }
            }
        });
    }), 30000);
    browser = await puppeteer.launch({ headless: true, executablePath: process.env.PUPPETEER_EXECUTABLE_PATH });

    for (const [width, height] of [[375, 812], [1440, 900]]) {
        await test(`${width}×${height}: protected seed/split/organization workflows and no uncertain retry`, async () => {
            const context = await browser.createBrowserContext();
            const page = await context.newPage();
            const errors = [];
            const applies = [];
            const organizeRequests = [];
            const moveRequests = [];
            const unexpected = [];
            let abortApply = false;
            let abortMove = false;
            let holdTrack = false;
            let heldTrack;
            let holdApply = false;
            let heldApply;
            page.on('pageerror', error => errors.push(error.message));
            page.on('dialog', async dialog => { errors.push(dialog.message()); await dialog.dismiss(); });
            await page.setViewport({ width, height });
            await page.setRequestInterception(true);
            page.on('request', request => {
                if (!request.url().startsWith(origin + '/')) {
                    unexpected.push(request.url());
                    request.abort();
                    return;
                }
                if (holdTrack && request.url().endsWith('/tracks')) { heldTrack = request; return; }
                if (request.url().endsWith('/apply')) {
                    applies.push(JSON.parse(request.postData()));
                    if (holdApply) { heldApply = request; return; }
                    if (abortApply) { request.abort(); return; }
                }
                if (request.url().endsWith('/playlists/organize')) organizeRequests.push(JSON.parse(request.postData()));
                if (request.url().endsWith('/playlists/move')) {
                    moveRequests.push(JSON.parse(request.postData()));
                    if (abortMove) { request.abort(); return; }
                }
                request.continue();
            });
            try {
                await page.goto(origin);
                assert.ok(page.url().endsWith('/unlock'));
                await page.type('input[name=token]', 'wrong');
                await page.click('button[type=submit]');
                await page.waitForFunction(() => document.querySelector('#unlockStatus').textContent.includes('Invalid access token'));
                assert.match(await page.content(), /Invalid access token/);
                await page.goto(origin + '/unlock');
                await page.type('input[name=token]', TOKEN);
                await Promise.all([page.waitForNavigation(), page.click('button[type=submit]')]);
                await page.waitForFunction(() => document.querySelector('#statusIndicator').textContent.includes('Online'));
                if (width < 600) await page.click('#menuToggle');
                await page.click('[data-view="playlist-plans"]');
                assert.equal(await page.$eval('#navMenu', el => el.classList.contains('show')), false);
                await page.click('#planLoadSources');
                await page.waitForFunction(() => document.querySelector('#planSource').options.length === 3);
                assert.equal(applies.length, 0);
                assert.match(await page.$eval('#planSource', el => el.textContent), /0123456789ABCDEF/);
                assert.equal(await page.$eval('#playlist-plans', el => el.querySelectorAll('img,script').length), 0);
                await page.select('#planSource', PID);
                await page.waitForFunction(() => document.querySelector('#planSeed').options.length === 2);
                await page.select('#planSeed', TID);
                await page.$eval('#planLimit', el => { el.value = '31'; el.dispatchEvent(new Event('input')); });
                assert.equal(await page.$eval('#planPreviewButton', el => el.disabled), true);
                await page.$eval('#planLimit', el => { el.value = '20'; el.dispatchEvent(new Event('input')); });
                await page.click('#planPreviewButton');
                await page.waitForFunction(() => !document.querySelector('#planReview').hidden);
                assert.equal(applies.length, 0);
                assert.equal(JSON.parse(await page.$eval('#planDetails', el => el.textContent)).limit, 20);
                if (process.env.CURATOR_SCREENSHOT_DIR) {
                    await page.evaluate(() => scrollTo(0, 0));
                    await page.screenshot({ path: join(process.env.CURATOR_SCREENSHOT_DIR, `curator-playlist-plan-${width}.png`), fullPage: true });
                }
                assert.equal(await page.$eval('#planApplyButton', el => el.disabled), true);
                await page.$eval('#planLimit', el => { el.value = '19'; el.dispatchEvent(new Event('input')); });
                assert.equal(await page.$eval('#planReview', el => el.hidden), true);
                await page.click('#planPreviewButton');
                await page.waitForFunction(() => !document.querySelector('#planReview').hidden);
                await page.click('#planConfirmed');
                await page.$eval('#planApplyButton', el => { el.click(); el.click(); });
                await page.waitForFunction(() => !document.querySelector('#planResult').hidden);
                assert.equal(applies.length, 1);
                assert.equal(applies[0].confirmed, true);
                assert.deepEqual(Object.keys(applies[0]).sort(), ['confirmed', 'plan_id']);
                assert.equal(JSON.parse(await page.$eval('#planReport', el => el.textContent)).success, true);
                assert.equal(await page.$eval('#planApplyButton', el => el.disabled), true);

                await page.evaluate(async token => {
                    await fetch('/unlock', {
                        method: 'POST', body: new URLSearchParams({ token }),
                        credentials: 'same-origin', mode: 'same-origin',
                    });
                }, TOKEN);
                await page.click('#planPreviewButton');
                await page.waitForFunction(() => document.querySelector('#planStatus').textContent.startsWith('Preview failed:'));
                assert.equal(applies.length, 1);
                await page.click('#planPreviewButton');
                await page.waitForFunction(() => !document.querySelector('#planReview').hidden);
                assert.equal(applies.length, 1);

                await page.select('#planKind', 'split');
                assert.equal(await page.$eval('#planPreviewButton', el => el.disabled), true);
                await page.select('#planSources', PID, '0000000000000002');
                await page.click('#planPreviewButton');
                await page.waitForFunction(() => !document.querySelector('#planReview').hidden);
                assert.equal(JSON.parse(await page.$eval('#planDetails', el => el.textContent)).sources.length, 2);
                await page.click('#planConfirmed');
                await page.click('#planApplyButton');
                await page.waitForFunction(() => !document.querySelector('#planResult').hidden);
                const report = JSON.parse(await page.$eval('#planReport', el => el.textContent));
                assert.equal(report.success, false);
                assert.equal(report.parts[0].status, 'unresolved');
                assert.equal(report.unresolved[0].action, 'add');
                assert.equal(applies.length, 2);
                await page.click('#planPreviewButton');
                await page.waitForFunction(() => !document.querySelector('#planReview').hidden);
                await page.click('#planConfirmed');
                abortApply = true;
                await page.click('#planApplyButton');
                await page.waitForFunction(() => !document.querySelector('#planResult').hidden);
                assert.match(await page.$eval('#planReport', el => el.textContent), /do not resubmit/);
                assert.equal(applies.length, 3);
                assert.equal(await page.$eval('#planApplyButton', el => el.disabled), true);
                abortApply = false;
                holdTrack = true;
                await page.select('#planKind', 'seed');
                const trackRequest = page.waitForRequest(request => request.url().endsWith('/tracks'));
                await page.select('#planSource', '0000000000000002');
                await trackRequest;
                await page.select('#planKind', 'split');
                await page.click('#planPreviewButton');
                await page.waitForFunction(() => !document.querySelector('#planReview').hidden);
                await page.click('#planConfirmed');
                holdApply = true;
                const applyRequest = page.waitForRequest(request => request.url().endsWith('/apply'));
                await page.click('#planApplyButton');
                await applyRequest;
                const warning = await page.$eval('#planStatus', el => el.textContent);
                assert.match(warning, /Submitting once/);
                const trackResponse = page.waitForResponse(response => response.url().endsWith('/tracks'));
                await heldTrack.continue();
                await trackResponse;
                await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
                assert.equal(await page.$eval('#planStatus', el => el.textContent), warning);
                holdApply = false;
                await heldApply.continue();
                await page.waitForFunction(() => !document.querySelector('#planResult').hidden);
                assert.equal(applies.length, 4);

                if (width < 600) await page.click('#menuToggle');
                await page.click('[data-view="organize"]');
                await page.click('#organizationLoadSources');
                await page.waitForFunction(() => document.querySelector('#organizationSources').options.length === 2);
                assert.equal(await page.$eval('#reviewChangesBtn', el => el.disabled), true);
                await page.select('#organizationSources', PID, '0000000000000002');
                assert.equal(await page.$eval('#confirmMoveBtn', el => el.disabled), true);
                await page.click('#reviewChangesBtn');
                await page.waitForFunction(() => document.getElementById('organizationPreview').style.display === 'block');
                assert.equal(organizeRequests.length, 1);
                assert.deepEqual(organizeRequests[0], { playlist_ids: [PID, '0000000000000002'], dry_run: true });
                assert.equal(JSON.parse(await page.$eval('#organizationPlanDetails', el => el.textContent)).version, 1);
                await page.select('#organizationSources', PID);
                assert.equal(await page.$eval('#organizationPreview', el => el.style.display), 'none');
                assert.equal(await page.$eval('#confirmMoveBtn', el => el.disabled), true);
                await page.click('#reviewChangesBtn');
                await page.waitForFunction(() => document.getElementById('organizationPreview').style.display === 'block');
                assert.equal(organizeRequests.length, 2);
                await page.click('#confirmMoveBtn');
                await page.waitForFunction(() => !document.getElementById('confirmModal').classList.contains('hidden'));
                await page.click('#confirmYes');
                await page.waitForFunction(() => document.getElementById('organizationResults').style.display === 'block');
                assert.equal(moveRequests.length, 1);
                assert.deepEqual(Object.keys(moveRequests[0]).sort(), ['confirmed', 'plan_id']);
                assert.equal(moveRequests[0].confirmed, true);
                assert.equal(JSON.parse(await page.$eval('#organizationResultsTable', el => el.textContent)).success, true);
                assert.equal(await page.$eval('#confirmMoveBtn', el => el.disabled), true);

                await page.click('#reviewChangesBtn');
                await page.waitForFunction(() => document.getElementById('organizationPreview').style.display === 'block');
                await page.click('#confirmMoveBtn');
                await page.waitForFunction(() => !document.getElementById('confirmModal').classList.contains('hidden'));
                abortMove = true;
                await page.click('#confirmYes');
                await page.waitForFunction(() => document.getElementById('organizationResultsSummary').textContent.includes('Failed or uncertain'));
                assert.equal(moveRequests.length, 2);
                abortMove = false;
                await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
                assert.equal(moveRequests.length, 2);
                assert.equal(await page.$eval('#confirmMoveBtn', el => el.disabled), true);

                assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
                assert.equal(await page.evaluate(token => JSON.stringify(localStorage).includes(token) || JSON.stringify(sessionStorage).includes(token), TOKEN), false);
                assert.deepEqual(errors, []);
                assert.deepEqual(unexpected, []);
            } finally {
                await context.close();
            }
        });
    }
} finally {
    if (browser) {
        const child = browser.process();
        try { await bounded(browser.close()); }
        catch {
            if (child && child.exitCode === null && child.signalCode === null) child.kill('SIGKILL');
            browser.disconnect();
        }
    }
    if (server && server.exitCode === null && server.signalCode === null) {
        const exited = once(server, 'exit');
        server.kill('SIGTERM');
        try { await bounded(exited); }
        catch { server.kill('SIGKILL'); await bounded(exited); }
    }
    await rm(directory, { recursive: true, force: true });
}
