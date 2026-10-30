#!/usr/bin/env python3
"""Convert LETools 1.5 uniques to LEB uniques_1_5.json.

Existing 1.4 entries are kept as-is; new IDs are formatted using templates
learned from (LETools mod, 1.4 LEB text) pairs on the same property/type/tags.
"""

import argparse
import json
import os
import re


def load(path):
	with open(path, encoding="utf-8") as f:
		return json.load(f)


def write_json(path, value):
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w", encoding="utf-8") as f:
		json.dump(value, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
		f.write("\n")


def num(value, percent):
	v = value * 100 if percent and abs(value) <= 1 else value
	if abs(v - round(v)) < 1e-9:
		return str(int(round(v)))
	return f"{v:.2f}".rstrip("0").rstrip(".")


def replace_numbers(sample, value, max_value):
	percent = "%" in sample
	lo = num(value, percent)
	hi = num(max_value, percent) if max_value not in (None, 0, value) else None
	m = re.match(r"^(.*?)(\(?-?\d+(?:\.\d+)?(?:-?\d+(?:\.\d+)?)?\)?)(.*)$", sample)
	if not m:
		return sample
	prefix, _, suffix = m.groups()
	number = f"({lo}-{hi})" if hi is not None else lo
	return prefix + number + suffix


def build_examples(leb, uniques):
	examples = {}
	for uid, entry in leb.items():
		src = uniques.get(str(uid))
		if not src:
			continue
		lmods = src.get("mods") or []
		bmods = entry.get("mods") or []
		if len(lmods) != len(bmods):
			continue
		for lm, bm in zip(lmods, bmods):
			key = (lm.get("property"), lm.get("type", 0), lm.get("tags", 0))
			examples.setdefault(key, (bm, lm))
	return examples


def format_mod(mod, examples, i18n, warnings):
	if mod.get("hideInTooltip"):
		return None
	key = (mod.get("property"), mod.get("type", 0), mod.get("tags", 0))
	example = examples.get(key)
	if example is None:
		# try the same property/type with any tags before giving up
		for k, v in examples.items():
			if k[0] == key[0] and k[1] == key[1]:
				example = v
				break
	if example is not None:
		sample = example[0]
		text = replace_numbers(sample, mod.get("value", 0), mod.get("maxValue", 0))
		return text.strip()
	warnings.append(key)
	name = i18n.get(f"Properties.Property_Player_{key[0]}_Name") or f"property {key[0]}"
	value = num(mod.get("value", 0), False)
	return f"+{value} {name}"


def convert(args):
	leb = load(os.path.join(args.leb_root, "src/Data/Uniques/uniques_1_4.json"))
	db = load(args.itemdb)
	i18n = load(args.i18n)
	uniques = (db.get("uniqueList") or {}).get("uniques") or {}
	examples = build_examples(leb, uniques)
	out = dict(leb)
	warnings = []

	for uid in sorted(uniques, key=lambda x: int(x)):
		if int(uid) <= 470 or uid in out:
			continue
		src = uniques[uid]
		name = i18n.get(src.get("displayNameKey")) or src.get("displayNameKey") or uid
		mods, roll_ids = [], []
		seen = set()
		for mod in src.get("mods") or []:
			text = format_mod(mod, examples, i18n, warnings)
			if text is None or text in seen:
				continue
			seen.add(text)
			mods.append(text)
			roll_ids.append(mod.get("rollId", 0))
		sub_types = src.get("subTypeIds") or []
		entry = {
			"name": name,
			"baseTypeID": src.get("baseTypeId"),
			"subTypeID": (sub_types[0] if sub_types else src.get("subTypeId", 0)),
			"req": {"level": src.get("levelRequirement", 0)},
			"mods": mods,
			"rollIds": roll_ids,
			"overrideLevelRequirement": bool(src.get("overrideLevelRequirement")),
		}
		descriptions = []
		for desc in src.get("tooltipDescriptions") or []:
			text = i18n.get(desc.get("descriptionKey"))
			if text:
				descriptions.append(text)
		if descriptions:
			entry["tooltipDescriptions"] = descriptions
		out[uid] = entry

	out_path = os.path.join(
		args.leb_root, "src/Data/Uniques", f"uniques_{args.version}.json"
	)
	write_json(out_path, out)
	print(f"wrote {out_path}: {len(out)} uniques ({len(out) - len(leb)} new)")
	for uid in ("477", "479"):
		if uid in out:
			print(uid, out[uid]["name"], "->", out[uid]["mods"])
	if warnings:
		missing = sorted(set(warnings))
		print(f"properties without a 1.4 example: {missing}")


def main():
	p = argparse.ArgumentParser()
	p.add_argument("--itemdb", required=True)
	p.add_argument("--i18n", required=True)
	p.add_argument("--leb-root", required=True)
	p.add_argument("--version", default="1_5")
	convert(p.parse_args())


if __name__ == "__main__":
	main()
