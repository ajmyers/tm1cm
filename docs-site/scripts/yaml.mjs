// The YAML the session files are written in, read without a dependency: comments, a map of keys
// to lists, list items that are maps of scalars, block scalars (key: |), and lists of scalars under an
// item's key (the lines typed into the shell). The live tests read the
// same files with PyYAML, and test/yaml.test.mjs checks both agree on every session.

export function load(text) {
	const lines = text.replaceAll('\r\n', '\n').split('\n');
	const root = {};
	let list = null;
	let item = null;
	let lastKey = null;
	for (let i = 0; i < lines.length; i++) {
		const line = lines[i];
		if (/^\s*(#.*)?$/.test(line)) continue;
		const top = /^([\w-]+):\s*$/.exec(line);
		if (top) {
			list = root[top[1]] = [];
			item = null;
			continue;
		}
		// A list of scalars under a step's key: "    key:" then "      - value" lines
		const scalarItem = /^\s{6,}- (.*)$/.exec(line);
		if (scalarItem && item && Array.isArray(item[lastKey])) {
			item[lastKey].push(scalarItem[1].replace(/^'(.*)'$/, '$1').replace(/^"(.*)"$/, '$1'));
			continue;
		}
		const entry = /^(\s*)(- )?([\w-]+):\s?(.*)$/.exec(line);
		if (!entry || !list) throw new Error('line ' + (i + 1) + ": can't read " + JSON.stringify(line));
		if (entry[2]) list.push((item = {}));
		const key = entry[3];
		const value = entry[4];
		lastKey = key;
		if (value === '' && !entry[2]) {
			item[key] = [];
		} else if (value === '|') {
			const indent = (lines[i + 1] ?? '').length - (lines[i + 1] ?? '').trimStart().length;
			const block = [];
			while (i + 1 < lines.length && (lines[i + 1].trim() === '' || lines[i + 1].length - lines[i + 1].trimStart().length >= indent)) {
				block.push(lines[++i].slice(indent));
			}
			while (block.length && block.at(-1).trim() === '') block.pop();
			item[key] = block.join('\n') + '\n';
		} else {
			item[key] = /^-?\d+$/.test(value) ? Number(value) : value.replace(/^'(.*)'$/, '$1').replace(/^"(.*)"$/, '$1');
		}
	}
	return root;
}
