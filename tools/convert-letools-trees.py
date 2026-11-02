#!/usr/bin/env python3
"""Convert the extracted LETools 1.5 data into LEB TreeData/1_5.

The 1.4 tree files provide the stable structure/mastery/start nodes; LETools
provides the current node stats, positions, class data, and skill trees.
"""

import argparse
import copy
import json
import os
import sys

# Stats LETools omits but the game still applies; keep in sync with
# REGRESSION_GUARDS.md. Keyed by full node key.
MANUAL_STATS = {
	"sbf4m-10": ["Base Poison Damage -> Cold"],
}

STAT_MAP = {
	"baseHealth": "baseHealth",
	"baseMana": "baseMana",
	"healthPerLevel": "healthPerLevel",
	"manaPerLevel": "manaPerLevel",
	"healthRegen": "healthRegen",
	"manaRegen": "manaRegen",
	"healthRegenPerLevel": "healthRegenPerLevel",
	"baseStrength": "baseStr",
	"baseDexterity": "baseDex",
	"baseIntelligence": "baseInt",
	"baseAttunement": "baseAtt",
	"baseVitality": "baseVit",
	"baseStunAvoidance": "baseStunAvoidance",
	"stunAvoidancePerLevel": "stunAvoidancePerLevel",
	"baseEndurance": "baseEndurance",
	"baseEnduranceThreshold": "baseEnduranceThreshold",
	"enduranceThresholdPerLevel": "enduranceThresholdPerLevel",
	"enduranceThresholdPerHealth": "enduranceThresholdPerHealth",
	"baseMoreDoTDamageTaken": "baseMoreDoTDamageTaken",
}


def load(path):
	with open(path, encoding="utf-8") as f:
		return json.load(f)


def write_json(path, value):
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w", encoding="utf-8") as f:
		json.dump(value, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
		f.write("\n")


def collect_ui_nodes(container):
	nodes = {}
	if isinstance(container, list):
		groups = container
	elif isinstance(container, dict) and "children" in container:
		groups = [container]
	else:
		groups = []
	for group in groups:
		for child in group.get("children") or []:
			nid = child.get("nodeId")
			if nid is not None and nid not in nodes:
				nodes[nid] = child
	return nodes


def transform_xy(child):
	rect = child.get("rect") if child else None
	if not rect or len(rect) < 2:
		return None
	return round(rect[0] * 0.8, 4), round(-rect[1] * 0.8, 4)


def stat_lines(node, tr):
	lines = []
	not_scaling = []
	for index, stat in enumerate(node.get("stats") or []):
		value = str(stat.get("value", "") or "")
		name = tr(stat.get("statNameKey"))
		if name and name.startswith("{"):
			name = name.strip("{}")
		if value and name:
			line = f"{value} {name}"
		else:
			line = value or name
		if stat.get("noScaling"):
			not_scaling.append(line.strip())
		else:
			lines.append(line.strip())
	return lines, not_scaling


def add_manual_stats(key, stats):
	for line in MANUAL_STATS.get(key, ()):
		if line not in stats:
			stats.append(line)


def reminder(node, tr):
	for key in ("descriptionKey", "altTextKey", "loreTextKey"):
		text = tr(node.get(key))
		if text:
			return [text]
	return []


def build_edges(nodes, prefix_for):
	# nodes: key -> {requirements: [{nodeID, requirement}], in/reqPoints/out}
	for node in nodes.values():
		if "_requirements" in node:
			node["in"] = []
			node["reqPoints"] = []
			node["out"] = []
	for key, node in nodes.items():
		for req in node.get("_requirements") or []:
			source = prefix_for(key, req.get("nodeID") or req.get("nodeId"))
			if source in nodes:
				nodes[source]["out"].append(key)
				node["in"].append(source)
				node["reqPoints"].append(req.get("requirement", 1))


def connect_starts(nodes, class_data, class_name):
	for start_name in [class_name] + [
		a.get("name") for a in class_data.get("ascendancies") or []
	]:
		start = nodes.get(start_name)
		if not start:
			continue
		for key in start.get("out") or []:
			target = nodes.get(key)
			if target is None:
				continue
			if start_name not in target.get("in", []):
				target.setdefault("in", []).append(start_name)
				target.setdefault("reqPoints", []).append(1)


def convert(args):
	raw = args.letools_raw
	i18n = load(args.i18n)
	char_trees = load(os.path.join(raw, "LECharTrees.json"))
	char_ui = load(os.path.join(raw, "LECharTreesUI.json"))
	skill_trees = load(os.path.join(raw, "LESkillTrees.json"))
	skill_ui = load(os.path.join(raw, "LESkillTreesUI.json"))
	abilities = load(os.path.join(raw, "LEAbilities.json")).get("abilityList") or {}

	def tr(key):
		if not key:
			return ""
		return i18n.get(key) or ""

	for entry in char_trees.get("trees") or []:
		ct = entry.get("characterTree") or {}
		cc = ct.get("characterClass") or {}
		class_id = cc.get("classID")
		tree_id = ct.get("treeID")
		old_path = os.path.join(
			args.leb_root, "src/TreeData", "1_4", f"tree_{class_id}.json"
		)
		old = load(old_path)
		tree = copy.deepcopy(old)
		class_data = tree["classes"][0]
		class_name = class_data.get("name") or tr(cc.get("classNameKey"))

		for src, dst in STAT_MAP.items():
			if cc.get(src) is not None:
				class_data[dst] = cc[src]
		class_data["name"] = class_name

		masteries = cc.get("masteries") or []
		asc = []
		for mastery in masteries:
			name = mastery.get("name") or tr(mastery.get("nameKey"))
			if name and name != class_name:
				asc.append({"id": name, "name": name})
		if asc:
			class_data["ascendancies"] = asc

		nodes = tree["nodes"]
		class_prefix = class_name + "-"
		char_nodes = ct.get("nodes") or {}
		ui_nodes = collect_ui_nodes((char_ui.get(tree_id) or {}).get("nodes"))
		removed = 0

		for node_id, src in char_nodes.items():
			key = class_prefix + str(node_id)
			node = nodes.get(key, {})
			stats, not_scaling = stat_lines(src, tr)
			node["skill"] = key
			node["name"] = tr(src.get("nodeNameKey")) or node.get("name", key)
			node["maxPoints"] = src.get("maxPoints", 0)
			node["mastery"] = src.get("mastery", 0)
			node["masteryRequirement"] = src.get("masteryRequirement", 0)
			node["stats"] = stats
			add_manual_stats(key, node["stats"])
			node["notScalingStats"] = not_scaling
			node["noScalingPointThreshold"] = src.get("noScalingPointThreshold", 0)
			node["_requirements"] = src.get("requirements") or []
			ui = ui_nodes.get(int(node_id))
			pos = transform_xy(ui)
			if pos:
				node["x"], node["y"] = pos
			if ui and not node.get("icon"):
				node["icon"] = ui.get("icon")
			text = reminder(src, tr)
			if text:
				node["reminderText"] = text
			if src.get("baseLockNode"):
				node["baseLockNode"] = True
			if src.get("lockNode"):
				node["lockNode"] = True
			nodes[key] = node

		for key in list(nodes):
			if key.startswith(class_prefix):
				node_id = key[len(class_prefix) :]
				if node_id.isdigit() and node_id not in char_nodes:
					del nodes[key]
					removed += 1

		# Class start / mastery start nodes: keep 1.4 stats, refresh outgoing roots.
		class_start = nodes.get(class_name)
		if class_start is not None:
			old_out = [k for k in (class_start.get("out") or []) if k in nodes]
			roots = [
				class_prefix + str(nid)
				for nid, src in char_nodes.items()
				if not (src.get("requirements") or [])
				and not src.get("masteryRequirement")
				and not src.get("mastery")
			]
			class_start["out"] = sorted(set(old_out) | set(roots))
			for key in class_start["out"]:
				if key in nodes and class_name not in nodes[key].get("in", []):
					nodes[key].setdefault("in", []).append(class_name)
					nodes[key].setdefault("reqPoints", []).append(1)

		for asc_entry in class_data.get("ascendancies") or []:
			name = asc_entry.get("name")
			start = nodes.get(name)
			if start is None:
				continue
			index = [a.get("name") for a in class_data.get("ascendancies") or []].index(name) + 1
			old_out = [k for k in (start.get("out") or []) if k in nodes]
			mastery_roots = [
				class_prefix + str(nid)
				for nid, src in char_nodes.items()
				if not (src.get("requirements") or [])
				and (src.get("masteryRequirement") == index or src.get("mastery") == index)
			]
			start["out"] = sorted(set(old_out) | set(mastery_roots))
			for key in start["out"]:
				if key in nodes and name not in nodes[key].get("in", []):
					nodes[key].setdefault("in", []).append(name)
					nodes[key].setdefault("reqPoints", []).append(1)

		# Skill trees for this class.
		old_skills = list(class_data.get("skills") or [])
		class_abilities = set()
		for a in cc.get("unlockableAbilities") or []:
			class_abilities.add(a.get("ability"))
		for m in masteries:
			for a in m.get("abilities") or []:
				class_abilities.add(a.get("ability"))
		for a in cc.get("knownAbilities") or []:
			class_abilities.add(a)
		for a in cc.get("defaultAbilities") or []:
			class_abilities.add(a)
		present = {s.get("treeId") for s in old_skills}
		for tid in sorted(t for t in class_abilities if t in skill_trees):
			if tid in present:
				continue
			ability_id = (skill_trees.get(tid) or {}).get("ability")
			ability = abilities.get(ability_id) or {}
			label = tr(ability.get("nameKey")) or tid
			old_skills.append({"name": label, "label": label, "treeId": tid})
			present.add(tid)
		class_data["skills"] = old_skills

		for tid in sorted(present):
			st = skill_trees.get(tid)
			if not st:
				continue
			ui_map = collect_ui_nodes(skill_ui.get(tid))
			prefix = tid + "-"
			skill_nodes = st.get("nodes") or {}
			for node_id, src in skill_nodes.items():
				key = prefix + str(node_id)
				node = nodes.get(key, {})
				stats, not_scaling = stat_lines(src, tr)
				node["skill"] = key
				node["name"] = tr(src.get("nodeNameKey")) or node.get("name", key)
				node["maxPoints"] = src.get("maxPoints", 0)
				node["mastery"] = src.get("mastery", 0)
				node["masteryRequirement"] = src.get("masteryRequirement", 0)
				node["stats"] = stats
				add_manual_stats(key, node["stats"])
				node["notScalingStats"] = not_scaling
				node["noScalingPointThreshold"] = src.get("noScalingPointThreshold", 0)
				node["_requirements"] = src.get("requirements") or []
				ui = ui_map.get(int(node_id))
				pos = transform_xy(ui)
				if pos:
					node["x"], node["y"] = pos
				if ui and not node.get("icon"):
					node["icon"] = ui.get("icon")
				text = reminder(src, tr)
				if text:
					node["reminderText"] = text
				nodes[key] = node
			for key in list(nodes):
				if key.startswith(prefix):
					node_id = key[len(prefix) :]
					if node_id.isdigit() and node_id not in skill_nodes:
						del nodes[key]

		build_edges(nodes, lambda key, nid: key.split("-")[0] + "-" + str(nid))
		connect_starts(nodes, class_data, class_name)
		for node in nodes.values():
			node.pop("_requirements", None)

		out_path = os.path.join(
			args.leb_root, "src/TreeData", args.version, f"tree_{class_id}.json"
		)
		write_json(out_path, tree)
		print(
			f"{class_name}: {len(nodes)} nodes "
			f"(removed {removed} passive), {len(class_data.get('skills') or [])} skills"
		)


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--letools-raw", required=True)
	parser.add_argument("--i18n", required=True)
	parser.add_argument("--leb-root", required=True)
	parser.add_argument("--version", default="1_5")
	convert(parser.parse_args())


if __name__ == "__main__":
	main()
