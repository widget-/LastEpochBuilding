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


def convert_bases(args):
	items = load_monobehaviour(os.path.join(args.assets, "MasterItemsList.asset"))
	old_path = os.path.join(args.leb_root, "src/Data/Bases/bases_1_4.json")
	old = load_json(old_path)

	out = {}
	new_names = []
	missing_implicits = []
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
			entry = {
				"type": base_type,
				"baseTypeID": base.get("baseTypeID"),
				"subTypeID": sub.get("subTypeID"),
				"req": {"level": sub.get("levelRequirement", 0)},
				"affixEffectModifier": base.get("affixEffectModifier", 0),
				"implicits": previous.get("implicits", []),
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
