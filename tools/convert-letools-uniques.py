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


def fmt_range(value, max_value, percent):
	lo = num(value, percent)
	if max_value in (None, 0, value):
		return lo
	hi = num(max_value, percent)
	return f"({lo}-{hi})"


def fmt_signed_range(value, max_value, percent):
	if value < 0 and (max_value is None or max_value < 0):
		lo, hi = sorted((value, max_value or value))
		a = num(lo, percent)
		b = num(hi, percent)
		return a if a == b else f"{a} to {b}"
	return fmt_range(value, max_value, percent)


def replace_numbers(sample, value, max_value):
	percent = "%" in sample
	if value < 0 and max_value is not None and max_value < 0 and (
		"less" in sample.lower() or "reduced" in sample.lower()
	):
		value, max_value = sorted((abs(value), abs(max_value)))
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
			key = (
				lm.get("property"),
				lm.get("type", 0),
				lm.get("tags", 0),
				lm.get("specialTag", 0),
			)
			examples.setdefault(key, (bm, lm))
	return examples


def format_from_table(mod, key, examples):
	example = examples.get(key)
	if example is None:
		return None
	sample = example[0]
	return replace_numbers(sample, mod.get("value", 0), mod.get("maxValue", 0)).strip()


def format_property(mod, meta, i18n, force_percent=False):
	"""Format a mod from a property-list entry (master or player)."""
	if not meta:
		return None
	name = i18n.get(meta.get("propertyNameKey"))
	if not name:
		return None
	value = mod.get("value", 0)
	max_value = mod.get("maxValue", 0)
	percent = bool(meta.get("displayAddedAsPercentage")) or force_percent
	if (
		meta.get("displayAsPercentageOf")
		and not meta.get("displayAddedAsTenthOfValue")
		and mod.get("type", 0) == 0
	):
		percent = True
	if "chance" in name.lower() and abs(value) <= 1:
		percent = True
	mod_type = mod.get("type", 0)
	if meta.get("hideModifierValue"):
		return name
	if mod_type == 2:
		word = "less" if meta.get("lessIsBetter") or value < 0 else "more"
		return f"{fmt_range(abs(value), abs(max_value), True)}% {word} {name}"
	if mod_type == 1:
		prefix = "" if name.lower().startswith(("increased", "reduced", "more", "less")) else "increased "
		return f"{fmt_range(value, max_value, True)}% {prefix}{name}"
	sign = "" if meta.get("dontDisplayPlus") else ("+" if value >= 0 else "")
	suffix = "%" if percent else ""
	return f"{sign}{fmt_signed_range(value, max_value, percent)}{suffix} {name}"


def format_mod(mod, examples, player_props, master_props, i18n, warnings, uid):
	if mod.get("hideInTooltip"):
		return None
	prop = mod.get("property")
	key = (prop, mod.get("type", 0), mod.get("tags", 0), mod.get("specialTag", 0))
	if prop == 88 and key[2] == 0 and key[3] == 0:
		return (
			f"+{fmt_range(mod.get('value', 0), mod.get('maxValue', 0), False)} "
			"to All Skills"
		)
	text = format_from_table(mod, key, examples)
	if text is not None:
		return text
	# Property 98 carries a player-property index in `tags`; 130/120 are plain
	# player properties whose name is not in the master item property list.
	if prop == 58:
		# Property 58 is a container whose specialTag picks an undocumented
		# variant; only the 1.4 examples and the two known Skeleton lines are
		# safe to render.
		if key[2] == 120 and key[3] == 21:
			text = "100% of Player Poison Damage Applies to Skeleton Rogues"
		elif key[2] == 120 and key[3] == 5:
			text = (
				f"({num(mod.get('value', 0) * 100, False)}-"
				f"{num(mod.get('maxValue', 0) * 100, False)})% of Player Poison "
				"Damage Applies to Skeleton Rogues"
			)
		else:
			text = None
	elif prop == 130 and prop < len(player_props):
		name = i18n.get(player_props[prop].get("propertyNameKey"))
		value = mod.get("value", 0) * 100
		max_value = mod.get("maxValue", 0) * 100
		text = (
			f"{fmt_signed_range(value, max_value, False)} {name}" if name else None
		)
	elif prop == 98 and isinstance(key[2], int) and key[2] < len(player_props):
		text = format_property(mod, player_props[key[2]], i18n)
	elif prop == 120 and prop < len(player_props):
		text = format_property(mod, player_props[prop], i18n)
	elif prop == 66 and mod.get("value", 0) < 0:
		text = f"{fmt_signed_range(mod.get('value', 0), mod.get('maxValue', 0), False)} Mana Cost"
	elif prop == 88:
		# A skill-level property whose tag group is not in the 1.4 examples.
		text = None
	else:
		text = format_property(mod, master_props.get(prop), i18n)
	if text is None:
		warnings.append((uid, key))
	return text


def convert(args):
	leb = load(os.path.join(args.leb_root, "src/Data/Uniques/uniques_1_4.json"))
	db = load(args.itemdb)
	i18n = load(args.i18n)
	core = load(args.core) if args.core else {}
	player_props = core.get("playerPropertyList") or []
	master_props = {
		entry["property"]: entry for entry in core.get("propertyList") or []
	}
	uniques = (db.get("uniqueList") or {}).get("uniques") or {}
	example_source = (
		load(args.examples_itemdb) if args.examples_itemdb else db
	)
	examples = build_examples(
		leb, (example_source.get("uniqueList") or {}).get("uniques") or {}
	)
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
			text = format_mod(mod, examples, player_props, master_props, i18n, warnings, uid)
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
		print(f"unresolved mods: {len(warnings)}")
		for uid, key in warnings:
			print(f"  ! {uid} {key}")


def main():
	p = argparse.ArgumentParser()
	p.add_argument("--itemdb", required=True)
	p.add_argument("--i18n", required=True)
	p.add_argument("--core", required=True)
	p.add_argument("--examples-itemdb", default=None)
	p.add_argument("--leb-root", required=True)
	p.add_argument("--version", default="1_5")
	convert(p.parse_args())


if __name__ == "__main__":
	main()
