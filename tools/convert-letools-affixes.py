#!/usr/bin/env python3
"""Generate ModItem_1_5 from the 1.4 table plus 1.5 affixes.

Existing affix/tier entries are kept verbatim. New affixes and missing tiers
are generated from the 1.5 Unity affix data, using the 1.4 text for the same
affix or the closest 1.4 pattern.
"""

import argparse
import json
import os
import re

import yaml


def load_mb(path):
	lines = [
		line
		for line in open(path, encoding="utf-8").read().splitlines()
		if not line.startswith("%") and not line.startswith("---")
	]
	for doc in yaml.safe_load_all("\n".join(lines)):
		if isinstance(doc, dict) and "MonoBehaviour" in doc:
			return doc["MonoBehaviour"]
	raise SystemExit(f"no MonoBehaviour in {path}")


def fmt(value, percent):
	v = value * 100 if percent and abs(value) < 1 else value
	if abs(v - round(v)) < 1e-9:
		return str(int(round(v)))
	return f"{v:.2f}".rstrip("0").rstrip(".")


def replace_first_number(text, lo, hi):
	m = re.match(r"^(.*?)(\(?-?\d+(?:\.\d+)?(?:-?\d+(?:\.\d+)?)?\)?)(.*)$", text)
	if not m:
		return text
	prefix, _, suffix = m.groups()
	percent = "%" in text
	a = fmt(lo, percent)
	b = fmt(hi, percent) if hi not in (None, 0, lo) else None
	number = f"({a}-{b})" if b is not None else a
	return prefix + number + suffix


def tier_text(minv, maxv, extra, percent=None):
	percent = ("%" in str(minv)) if percent is None else percent
	lo = fmt(minv, percent)
	hi = fmt(maxv, percent) if maxv not in (None, 0, minv) else None
	prefix = "+" if minv >= 0 else ""
	if hi is None:
		return f"{prefix}{lo}"
	return f"{prefix}({lo}-{hi})"


def affix_text(name, tier):
	minv = tier.get("minRoll", 0)
	maxv = tier.get("maxRoll", 0)
	extra = (tier.get("extraRolls") or [None])[0]
	lines = []

	if "Level of " in name:
		skill = name.split("Level of ", 1)[1]
		lines.append(f"+{fmt(minv, False)} to {skill}")
		if extra:
			lines.append(
				f"{{rounding:Integer}}({fmt(extra.get('minRoll', 0), True)}-"
				f"{fmt(extra.get('maxRoll', 0), True)})% increased Melee Damage"
			)
	elif name.startswith("Blood Rage"):
		lines.append(name)
	elif name.startswith("Caretaker's"):
		lines.append(f"+({fmt(minv, True)}-{fmt(maxv, True)})% {name}")
		if extra:
			lines.append(f"+{fmt(extra.get('minRoll', 0), False)} {name}")
	elif "Mana and Mana Regen" in name:
		lines.append(f"{{rounding:Integer}}({fmt(minv, True)})% increased Mana")
		if extra:
			lines.append(
				f"{{rounding:Integer}}({fmt(extra.get('minRoll', 0), True)}-"
				f"{fmt(extra.get('maxRoll', 0), True)})% increased Mana Regen"
			)
	elif " per " in name:
		flat = name.startswith(("Strength", "Dexterity", "Vitality", "Armor"))
		value = tier_text(minv, maxv, extra, percent=not flat)
		lines.append(f"{value} {name}" if flat else f"{value}% {name}")
	else:
		lines.append(f"{tier_text(minv, maxv, extra)}% {name}")
	return lines


def convert(args):
	leb = json.load(open(os.path.join(args.leb_root, "src/Data/ModItem_1_4.json")))
	asset = load_mb(args.affixes)
	by_id = {}
	for group in ("singleAffixes", "multiAffixes"):
		for entry in asset.get(group) or []:
			by_id[entry.get("affixId")] = entry
	db = json.load(open(args.itemdb))
	affix_list = db.get("affixList") or {}
	where = {}
	for group in ("singleAffixes", "multiAffixes"):
		for key, entry in (affix_list.get(group) or {}).items():
			where[int(key)] = entry

	# Templates keyed by affix id (first available tier).
	templates = {}
	for key, entry in leb.items():
		aid = int(key.split("_")[0])
		templates.setdefault(aid, entry)
	by_name = {}
	for key, entry in leb.items():
		by_name.setdefault(entry.get("affixName"), entry)

	out = dict(leb)
	added = 0
	for aid in sorted(by_id):
		src = by_id[aid]
		leet = where.get(aid) or {}
		# Unique-specific affixes duplicate data that lives in uniques_*.json and
		# their stat text is not generatable from the affix name.
		if leet.get("forUniqueId"):
			continue
		tiers = src.get("tiers") or []
		can_roll = leet.get("canRollOn")
		template = templates.get(aid) or by_name.get(src.get("affixName"))
		for tier_index, tier in enumerate(tiers):
			key = f"{aid}_{tier_index}"
			if key in out:
				continue
			if (src.get("affixName") or "").startswith("Blood Rage") and leet.get("va"):
				# Blood Rage affixes carry an internal asset name but the display
				# name ("You have Berserking Rage") is the in-game stat line.
				lines = [leet["va"]]
			elif template is not None and template.get("1"):
				first = replace_first_number(
					template["1"],
					tier.get("minRoll", 0),
					tier.get("maxRoll", 0),
				)
				lines = [first]
				extra = (tier.get("extraRolls") or [None])[0]
				if extra and template.get("2"):
					lines.append(
						replace_first_number(
							template["2"],
							extra.get("minRoll", 0),
							extra.get("maxRoll", 0),
						)
					)
			else:
				lines = affix_text(src.get("affixName") or "", tier)
			entry = {
				"affixName": src.get("affixName"),
				"modName": template.get("modName") if template else src.get("affixTitle"),
				"affix": template.get("affix") if template else src.get("affixTitle"),
				"1": lines[0],
				"level": src.get("levelRequirement", 0),
				"statOrderKey": template.get("statOrderKey", aid) if template else aid,
				"statOrder": template.get("statOrder", [aid]) if template else [aid],
				"tier": tier_index,
				"type": "Prefix" if src.get("type", 0) == 0 else "Suffix",
				"standardAffixEffectModifier": src.get("standardAffixEffectModifier", 0),
				"canRollOn": can_roll if can_roll is not None else (template or {}).get("canRollOn", []),
				"specialAffixType": src.get("specialAffixType", 0),
				"classSpecificity": leet.get("classSpecificity", (template or {}).get("classSpecificity", 0)),
			}
			if len(lines) > 1:
				entry["2"] = lines[1]
			out[key] = entry
			added += 1

	path = os.path.join(args.leb_root, "src/Data", f"ModItem_{args.version}.json")
	with open(path, "w", encoding="utf-8") as f:
		json.dump(out, f, ensure_ascii=False, indent="\t")
		f.write("\n")
	print(f"wrote {path}: {len(out)} entries ({len(leb)} existing, {added} added)")


def main():
	p = argparse.ArgumentParser()
	p.add_argument("--affixes", required=True)
	p.add_argument("--itemdb", required=True)
	p.add_argument("--leb-root", required=True)
	p.add_argument("--version", default="1_5")
	convert(p.parse_args())


if __name__ == "__main__":
	main()
