// The reference's search box (site.mjs searchBox), styled as skipcheck-tm1's docs search: finds
// settings, filters, options, exit codes and walkthroughs by name or by words of their
// description, from /tm1cm/search.json (reference.mjs). "/" focuses it; arrows and Enter pick.
(() => {
	const box = document.querySelector('.search');
	if (!box) return;
	const input = box.querySelector('input');
	const list = box.querySelector('[role="listbox"]');
	const none = box.querySelector('.none');
	box.hidden = false;
	let index = null;
	let active = -1;
	const load = () => (index ??= fetch(input.dataset.index).then((r) => r.json()));
	const score = (entry, words) => {
		const title = entry.title.toLowerCase();
		const text = (entry.summary + ' ' + entry.page).toLowerCase();
		let total = 0;
		for (const word of words) {
			if (title === word) total += 10;
			else if (title.startsWith(word)) total += 6;
			else if (title.includes(word)) total += 4;
			else if (text.includes(word)) total += 1;
			else return 0;
		}
		return total;
	};
	const select = (i) => {
		const options = [...list.children];
		active = options.length ? (i + options.length) % options.length : -1;
		options.forEach((o, n) => o.setAttribute('aria-selected', String(n === active)));
		options[active]?.scrollIntoView({ block: 'nearest' });
	};
	const show = async () => {
		const words = input.value.toLowerCase().split(/\s+/).filter(Boolean);
		list.replaceChildren();
		active = -1;
		if (!words.length) {
			list.hidden = none.hidden = true;
			input.setAttribute('aria-expanded', 'false');
			return;
		}
		const found = (await load()).map((e) => [score(e, words), e]).filter(([s]) => s > 0).sort((a, b) => b[0] - a[0]).slice(0, 10);
		for (const [, entry] of found) {
			const option = document.createElement('li');
			option.setAttribute('role', 'option');
			const link = document.createElement('a');
			link.href = entry.url;
			const title = document.createElement(entry.page === 'Walkthrough' ? 'span' : 'code');
			title.className = 'title';
			title.textContent = entry.title;
			const where = document.createElement('span');
			where.className = 'where';
			where.textContent = entry.page;
			const summary = document.createElement('span');
			summary.className = 'summary';
			summary.textContent = entry.summary.length > 140 ? entry.summary.slice(0, 137) + '…' : entry.summary;
			link.append(title, where, summary);
			option.append(link);
			list.append(option);
		}
		list.hidden = found.length === 0;
		none.hidden = found.length > 0;
		input.setAttribute('aria-expanded', String(found.length > 0));
	};
	input.addEventListener('input', show);
	input.addEventListener('focus', load);
	input.addEventListener('keydown', (event) => {
		if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
			event.preventDefault();
			select(active + (event.key === 'ArrowDown' ? 1 : -1));
		} else if (event.key === 'Enter' && list.children[Math.max(active, 0)]) {
			event.preventDefault();
			location.href = list.children[Math.max(active, 0)].querySelector('a').href;
		} else if (event.key === 'Escape') {
			list.hidden = none.hidden = true;
		}
	});
	document.addEventListener('keydown', (event) => {
		if (event.key === '/' && document.activeElement !== input) {
			event.preventDefault();
			input.focus();
		}
	});
})();
