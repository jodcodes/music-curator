(() => {
    const form = document.getElementById('unlockForm');
    const status = document.getElementById('unlockStatus');
    const button = form.querySelector('button');
    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (button.disabled) return;
        button.disabled = true;
        const body = new URLSearchParams(new FormData(form));
        form.reset();
        status.textContent = 'Unlocking…';
        try {
            // Fetch preserves Origin under no-referrer, unlike native form navigation.
            const response = await fetch('/unlock', {
                method: 'POST', body,
                credentials: 'same-origin', mode: 'same-origin',
                cache: 'no-store', redirect: 'manual',
                signal: AbortSignal.timeout(30000),
            });
            if (response.type === 'opaqueredirect') {
                window.location.assign('/');
                return;
            }
            const result = await response.json();
            status.textContent = result.error || 'Unlock failed.';
        } catch {
            status.textContent = 'Unlock request failed. Check the local server before trying again.';
        } finally {
            body.delete('token');
            button.disabled = false;
        }
    });
})();
