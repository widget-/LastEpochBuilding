#!/usr/bin/env python3
"""Convert AssetRipper-exported Last Epoch assets into LEB's versioned JSON.

The source is the full Unity-project export, e.g.
~/le-dump/export-perma-full/ExportedProject/Assets.

Usage:
  python3 tools/convert-game-data.py bases \
    --assets ~/le-dump/export-perma-full/ExportedProject/Assets \
    --leb-root . --version 1_5

Requires PyYAML (nix shell nixpkgs#python3Packages.pyyaml -c python3 ...).
"""

import argparse
import json
import os
import sys

try:
	import yaml
except ImportError:
	sys.exit("PyYAML is required (nix shell nixpkgs#python3Packages.pyyaml -c python3 ...)")


def load_monobehaviour(path):
	text = open(path, encoding="utf-8").read()
	lines = [
		line
		for line in text.splitlines()
		if not line.startswith("%") and not line.startswith("---")
	]
	for doc in yaml.safe_load_all("\n".join(lines)):
		if isinstance(doc, dict) and "MonoBehaviour" in doc:
			return doc["MonoBehaviour"]
	raise SystemExit(f"no MonoBehaviour document in {path}")


def load_json(path):
	with open(path, encoding="utf-8") as f:
		return json.load(f)


def write_json(path, value):
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w", encoding="utf-8") as f:
		json.dump(value, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
		f.write("\n")


# Tag bits used by the item implicit properties. Derived from the 1.4 bases,
# which already carry the formatted text for the same tag combinations.
TAG_SOURCES = (
	(8192, "Minion"),
	(256, "Spell"),
	(512, "Melee"),
	(1024, "Throwing"),
	(2048, "Bow"),
	(16384, "Totem"),
)
TAG_DAMAGE = (
	(1, "Physical"),
	(2, "Lightning"),
	(4, "Cold"),
	(8, "Fire"),
	(16, "Void"),
	(32, "Necrotic"),
	(64, "Poison"),
	(128, "Elemental"),
)
AILMENTS = {
	1: "Ignite",
	2: "inflict Bleed",
	3: "Chill",
	5: "Shock",
	6: "Slow",
	7: "Poison",
	8: "Shred Armor",
	10: "apply Future Strike",
	16: "apply Frailty",
	23: "apply Frostbite",
	28: "Shred Poison Resistance",
	29: "Shred Necrotic Resistance",
	30: "Shred Void Resistance",
	42: "Shred Fire Resistance",
	73: "Shred Physical Resistance",
	74: "Shred Cold Resistance",
	75: "Shred Lightning Resistance",
}
HIT_SUFFIX = {256: "Spell Hit", 512: "Melee Hit", 1024: "Throwing Hit", 2048: "Bow Hit", 8192: "Minion Hit"}


def fmt_number(value, percent):
	x = value * 100 if percent else value
	if abs(x - round(x)) < 1e-9:
		return str(int(round(x)))
	return f"{x:.2f}".rstrip("0").rstrip(".")


def fmt_roll(min_value, max_value, percent):
	lo = fmt_number(min_value, percent)
	if max_value is None or max_value == min_value:
		return lo
	return f"({lo}-{fmt_number(max_value, percent)})"


def fmt_abs_roll(min_value, max_value):
	lo, hi = sorted((abs(min_value), abs(max_value)))
	return fmt_roll(lo, hi, True)


def tag_labels(tags, table):
	return [label for bit, label in table if tags & bit]


def implicit_line(rec, properties):
	"""Format one implicit record the way the 1.4 bases are written.

	Returns None when the property is not one we know how to render.
	"""
	prop = rec.get("property")
	mod_type = rec.get("type", 0)
	tags = rec.get("tags", 0)
	special = rec.get("specialTag", 0)
	min_value = rec.get("implicitValue", 0)
	max_value = rec.get("implicitMaxValue", min_value)
	meta = properties.get(prop, {})
	percent = bool(meta.get("displayAddedAsPercentage")) or mod_type in (1, 2)

	if prop == 1:  # Ailment Chance
		ailment = AILMENTS.get(special)
		if not ailment:
			return None
		hit = HIT_SUFFIX.get(tags, "Hit")
		return f"+{fmt_roll(min_value, max_value, True)}% Chance to {ailment} on {hit}"

	if prop == 0:  # Damage
		name = " ".join(
			tag_labels(tags, TAG_SOURCES) + tag_labels(tags, TAG_DAMAGE) + ["Damage"]
		)
		if mod_type == 1:
			return f"{fmt_roll(min_value, max_value, True)}% increased {name}"
		return f"+{fmt_roll(min_value, max_value, percent)} {name}"

	if prop in (59, 131):  # Penetration / Global Conditional Penetration
		name = " ".join(tag_labels(tags, TAG_SOURCES) + tag_labels(tags, TAG_DAMAGE) + ["Penetration"])
		return f"+{fmt_roll(min_value, max_value, True)}% {name}"

	if prop in (4, 132):  # Critical Strike Chance (+ conditional variant)
		source = " ".join(tag_labels(tags, TAG_SOURCES))
		name = (source + " " if source else "") + "Critical Strike Chance"
		if mod_type == 1:
			return f"{fmt_roll(min_value, max_value, True)}% increased {name}"
		if mod_type == 2:
			word = "less" if min_value < 0 else "more"
			return f"{fmt_abs_roll(min_value, max_value)}% {word} {name}"
		return f"+{fmt_roll(min_value, max_value, True)}% {name}"

	if prop in (5, 133):  # Critical Strike Multiplier (+ conditional variant)
		source = " ".join(tag_labels(tags, TAG_SOURCES))
		name = (source + " " if source else "") + "Critical Strike Multiplier"
		return f"+{fmt_roll(min_value, max_value, True)}% {name}"

	if prop in (2, 3):  # Attack / Cast Speed
		name = meta.get("propertyName") or ""
		source = " ".join(tag_labels(tags, TAG_SOURCES))
		prefix = f"{source} " if source else ""
		return f"{fmt_roll(min_value, max_value, True)}% increased {prefix}{name}"

	if prop == 66:  # Mana Cost
		source = " ".join(tag_labels(tags, TAG_SOURCES))
		prefix = f"{source} " if source else ""
		sign = "+" if min_value >= 0 else ""
		return f"{sign}{fmt_roll(min_value, max_value, percent)} {prefix}Mana Cost"

	if prop == 98:  # Global Conditional Echo Damage
		word = "less" if min_value < 0 else "more"
		return (
			f"{fmt_abs_roll(min_value, max_value)}% {word} "
			"Echo Damage when a skill is Echoed"
		)

	if prop == 58 and tags == 782 and special == 0:  # deprecated ID reused for Evade Charge
		return f"+{fmt_roll(min_value, max_value, False)} Evade Charge"

	name = meta.get("propertyName") or ""
	if not name:
		return None
	name = name.replace("Global Conditional ", "")
	if mod_type == 1:
		return f"{fmt_roll(min_value, max_value, True)}% increased {name}"
	if mod_type == 2:
		word = "less" if min_value < 0 else "more"
		return f"{fmt_abs_roll(min_value, max_value)}% {word} {name}"
	sign = "+" if min_value >= 0 else ""
	suffix = "%" if percent else ""
	return f"{sign}{fmt_roll(min_value, max_value, percent)}{suffix} {name}"


def implicit_lines(sub, properties, unsupported):
	lines = []
	for rec in sub.get("implicits") or []:
		line = implicit_line(rec, properties)
		if line is None:
			unsupported.add(rec.get("property"))
			continue
		if line not in lines:  # duplicate records would double-count
			lines.append(line)
	return lines


def load_properties(leb_root):
	path = os.path.join(
		leb_root, "src/Data/Properties/property_list_1_4.json"
	)
	data = load_json(path)
	return {entry["property"]: entry for entry in data.get("properties") or []}


def convert_bases(args):
	items = load_monobehaviour(os.path.join(args.assets, "MasterItemsList.asset"))
	old_path = os.path.join(args.leb_root, "src/Data/Bases/bases_1_4.json")
	old = load_json(old_path)
	properties = load_properties(args.leb_root)

	out = {}
	new_names = []
	missing_implicits = []
	unsupported = set()
	field_mismatches = []

	for base in items.get("EquippableItems") or []:
		base_type = base.get("displayName") or base.get("BaseTypeName")
		if not base_type:
			continue
		for sub in base.get("subItems") or []:
			name = sub.get("displayName") or sub.get("name")
			if not name or name == "None":
				continue
			previous = old.get(name, {})
			implicits = previous.get("implicits", [])
			if not previous and sub.get("implicits"):
				implicits = implicit_lines(sub, properties, unsupported)
			entry = {
				"type": base_type,
				"baseTypeID": base.get("baseTypeID"),
				"subTypeID": sub.get("subTypeID"),
				"req": {"level": sub.get("levelRequirement", 0)},
				"affixEffectModifier": base.get("affixEffectModifier", 0),
				"implicits": implicits,
			}
			# The export lacks these LEB-only fields; carry them from 1.4.
			for field in ("weapon", "hidden", "timeline"):
				if previous.get(field) is not None:
					entry[field] = previous[field]
			if previous.get("legacy") or sub.get("isLegacySubType") or sub.get("obsoleteItem"):
				entry["legacy"] = True
			class_req = sub.get("classRequirement", 0)
			if class_req:
				entry["classReq"] = class_req

			out[name] = entry
			if not previous:
				new_names.append(name)
				if not entry["implicits"]:
					missing_implicits.append(name)
			else:
				for field in ("type", "baseTypeID", "subTypeID", "classReq", "affixEffectModifier"):
					if previous.get(field) != entry.get(field):
						field_mismatches.append(
							(name, field, previous.get(field), entry.get(field))
						)

	out_path = os.path.join(
		args.leb_root, "src/Data/Bases", f"bases_{args.version}.json"
	)
	write_json(out_path, out)

	print(f"wrote {out_path}: {len(out)} bases")
	print(f"1.4 bases: {len(old)}; new in {args.version}: {len(new_names)}")
	for name in new_names[:40]:
		print(f"  + {name}")
	if len(new_names) > 40:
		print(f"  ... {len(new_names) - 40} more")
	if missing_implicits:
		print(f"new bases without 1.4 implicits (need formatting): {len(missing_implicits)}")
		for name in missing_implicits[:20]:
			print(f"  ! {name}")
	if unsupported:
		print(f"implicit properties without a formatter: {sorted(unsupported)}")
	if field_mismatches:
		print(f"field mismatches for same-named bases: {len(field_mismatches)}")
		for name, field, before, after in field_mismatches[:20]:
			print(f"  ~ {name}: {field} {before!r} -> {after!r}")


def main():
	parser = argparse.ArgumentParser()
	sub = parser.add_subparsers(dest="command", required=True)

	bases = sub.add_parser("bases", help="MasterItemsList.asset -> bases_<version>.json")
	bases.add_argument("--assets", required=True)
	bases.add_argument("--leb-root", required=True)
	bases.add_argument("--version", default="1_5")
	bases.set_defaults(func=convert_bases)

	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
