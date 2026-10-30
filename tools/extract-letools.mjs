#!/usr/bin/env node
// Extract the data globals embedded in Last Epoch Tools bundles.
//
// The planner and DB pages ship their data inline as window.* object literals:
//   planner  -> LECharTrees, LESkillTrees, LEAbilities, LEWeaverTree, bonuses
//   db       -> coreDB (property formatting metadata)
// The itemDB itself is copied from /db/ as JSON.
//
// This script only lifts those literals into JSON; it does not convert them to
// LEB's format.
//
// Inputs are local files, not URLs:
//   --planner-js   data/versionNNN/planner/js/<hash>.js from lastepochtools.com
//   --db-js        data/versionNNN/db/js/<hash>.js containing window.coreDB
//   --itemdb       the `window.itemDB` object from /db/ (copied from the console)
//   --i18n         data/versionNNN/i18n/full/en.json?14
//   --out          output directory (kept outside the repo)
//
// Cloudflare may challenge automated clients; obtaining the bundles once by
// hand is an accepted input path.
//
// Usage:
//   node tools/extract-letools.mjs \
//     --planner-js /tmp/planner.js --db-js /tmp/db.js \
//     --itemdb /tmp/itemdb.json --i18n /tmp/en.json \
//     --out /tmp/letools-1_5 --version 1_5 --letools-version 152

import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import vm from "node:vm";

const PLANNER_GLOBALS = [
	"LECharTrees",
	"LECharTreesUI",
	"LESkillTrees",
	"LESkillTreesUI",
	"LEAbilities",
	"LEWeaverTree",
	"LEWeaverTreeUI",
	"skillBonuses",
	"passiveBonuses",
	"partialSkillBonuses",
	"UIBuffs",
	"UIBuffIds",
	"LETooltipIcons",
	"LocalSP",
];

const DB_GLOBALS = ["coreDB"];

function usage(message) {
	if (message) console.error(`error: ${message}\n`);
	console.error(
		"usage: node tools/extract-letools.mjs --planner-js FILE [--db-js FILE] " +
			"--itemdb FILE --i18n FILE --out DIR [--version 1_5] [--letools-version 152]"
	);
	process.exit(2);
}

function parseArgs(argv) {
	const out = {};
	for (let i = 0; i < argv.length; i++) {
		const arg = argv[i];
		if (!arg.startsWith("--")) usage(`unexpected argument ${arg}`);
		const key = arg.slice(2);
		const value = argv[++i];
		if (value === undefined) usage(`missing value for ${arg}`);
		out[key] = value;
	}
	for (const required of ["planner-js", "itemdb", "i18n", "out"]) {
		if (!out[required]) usage(`missing --${required}`);
	}
	return out;
}

// Take the initializer of `window.NAME=...` up to the top-level semicolon.
// Strings, template literals, and nested brackets are skipped; the data in
// these bundles is a pure object/array literal.
function extractLiteral(src, name) {
	const marker = `window.${name}=`;
	const at = src.indexOf(marker);
	if (at < 0) throw new Error(`${name} not found in bundle`);

	let i = at + marker.length;
	while (/\s/.test(src[i])) i++;
	const start = i;
	let depth = 0;
	let quote = null;
	let escaped = false;

	for (; i < src.length; i++) {
		const c = src[i];
		if (quote) {
			if (escaped) escaped = false;
			else if (c === "\\") escaped = true;
			else if (c === quote) quote = null;
			continue;
		}
		if (c === '"' || c === "'" || c === "`") {
			quote = c;
			continue;
		}
		if (c === "{" || c === "[" || c === "(") depth++;
		else if (c === "}" || c === "]" || c === ")") depth--;
		else if (c === ";" && depth === 0) break;
	}

	if (quote || depth !== 0) throw new Error(`${name}: unbalanced literal`);
	const expr = src.slice(start, i);
	if (!/^[\[{]/.test(expr)) throw new Error(`${name}: not an object/array literal`);
	return expr;
}

function evaluateLiteral(expr, name) {
	// A fresh context has standard JS built-ins but no process/require/fs.
	const context = vm.createContext({});
	return vm.runInContext(`(${expr})`, context, {
		filename: name,
		timeout: 20000,
	});
}

function sha256(file) {
	return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

function writeJson(file, value) {
	fs.writeFileSync(file, JSON.stringify(value));
	return fs.statSync(file).size;
}

function extractBundle(file, names, disabled, rawDir, globals) {
	const src = fs.readFileSync(file, "utf8");
	for (const name of names) {
		if (disabled.has(name)) continue;
		const expr = extractLiteral(src, name);
		const value = evaluateLiteral(expr, name);
		const bytes = writeJson(path.join(rawDir, `${name}.json`), value);
		globals[name] = { bytes };
		console.log(`  ${name.padEnd(20)} ${bytes} bytes`);
	}
	return src;
}

function main() {
	const args = parseArgs(process.argv.slice(2));
	const outDir = args.out;
	const rawDir = path.join(outDir, "raw");
	fs.mkdirSync(rawDir, { recursive: true });

	const disabled = new Set((args["skip"] || "").split(",").filter(Boolean));
	const globals = {};

	const plannerJs = args["planner-js"];
	const plannerSrc = extractBundle(plannerJs, PLANNER_GLOBALS, disabled, rawDir, globals);

	let dbJs = null;
	let dbSrc = null;
	if (args["db-js"]) {
		dbJs = args["db-js"];
		dbSrc = extractBundle(dbJs, DB_GLOBALS, disabled, rawDir, globals);
	}

	const itemDb = JSON.parse(fs.readFileSync(args.itemdb, "utf8"));
	const itemDbBytes = writeJson(path.join(outDir, "itemdb.json"), itemDb);

	const i18n = JSON.parse(fs.readFileSync(args.i18n, "utf8"));
	const i18nBytes = writeJson(path.join(outDir, "i18n.json"), i18n);

	const sources = {
		plannerJs: {
			file: path.basename(plannerJs),
			bytes: Buffer.byteLength(plannerSrc),
			sha256: sha256(plannerJs),
		},
		itemdb: { file: path.basename(args.itemdb), bytes: itemDbBytes, sha256: sha256(args.itemdb) },
		i18n: { file: path.basename(args.i18n), bytes: i18nBytes, sha256: sha256(args.i18n) },
	};
	if (dbJs) {
		sources.dbJs = {
			file: path.basename(dbJs),
			bytes: Buffer.byteLength(dbSrc),
			sha256: sha256(dbJs),
		};
	}

	const manifest = {
		version: args.version || null,
		letoolsVersion: args["letools-version"] || null,
		generatedAt: new Date().toISOString(),
		sources,
		globals,
	};
	writeJson(path.join(outDir, "manifest.json"), manifest);

	console.log(`\nwrote ${path.resolve(outDir)}`);
	console.log(`  itemdb ${itemDbBytes} bytes, i18n ${i18nBytes} bytes`);
}

try {
	main();
} catch (error) {
	console.error(`error: ${error.message}`);
	process.exit(1);
}
