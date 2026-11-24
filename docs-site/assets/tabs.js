// The system tabs (macOS and Linux, Windows) on install steps and commands, as skipcheck-tm1's
// language tabs work: choosing one chooses it on every box, on this page and the next, and the
// choice is remembered. Until one is chosen, the reader's own system. Without JavaScript every
// panel shows.
const KEY = 'tm1cm-system';

function show(system) {
	for (const group of document.querySelectorAll('.tabs')) {
		const tabs = [...group.querySelectorAll('[role="tab"]')];
		const chosen = tabs.find((tab) => tab.dataset.tab === system) ?? tabs[0];
		if (!chosen) continue;
		for (const tab of tabs) {
			const selected = tab === chosen;
			tab.setAttribute('aria-selected', String(selected));
			tab.tabIndex = selected ? 0 : -1;
		}
		for (const panel of group.querySelectorAll('[role="tabpanel"]')) panel.hidden = panel.dataset.tab !== chosen.dataset.tab;
	}
}

function stored() {
	try {
		return localStorage.getItem(KEY);
	} catch {
		return null;
	}
}

document.addEventListener('click', (event) => {
	const tab = event.target instanceof Element ? event.target.closest('.tabs [role="tab"]') : null;
	if (!tab) return;
	const before = tab.getBoundingClientRect().top;
	try {
		localStorage.setItem(KEY, tab.dataset.tab);
	} catch {
		// storage is off
	}
	show(tab.dataset.tab);
	window.scrollBy(0, tab.getBoundingClientRect().top - before);
});

document.addEventListener('keydown', (event) => {
	if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
	const tab = event.target instanceof Element ? event.target.closest('.tabs [role="tab"]') : null;
	if (!tab) return;
	const tabs = [...tab.parentElement.querySelectorAll('[role="tab"]')];
	const next = tabs[(tabs.indexOf(tab) + (event.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
	next.focus();
	next.click();
});

show(stored() ?? (/Win/.test(navigator.userAgentData?.platform ?? navigator.platform ?? '') ? 'windows' : 'unix'));
