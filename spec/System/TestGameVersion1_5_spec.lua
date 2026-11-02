-- Locks the 1.5 data set: the version must be loadable/offered as latest,
-- the converted bases/uniques must be present, and the LETools tree data must
-- not feed display-only noScaling stats into the parser.

local function buildXML()
	return [[<?xml version="1.0" encoding="UTF-8"?>
<LastEpochBuilding>
	<Build level="100" targetVersion="1_5" className="Primalist" ascendClassName="Druid" mainSocketGroup="1" viewMode="TREE" characterLevelAutoMode="false"/>
	<Skills activeSkillSet="1">
		<SkillSet id="1">
			<Skill skillId="Swipe" slot="Skill 1" mainActiveSkill="1" includeInFullDPS="true" index="1" enabled="true"/>
		</SkillSet>
	</Skills>
	<Tree activeSpec="1">
		<Spec treeVersion="1_5" classId="0" ascendClassId="3" nodes="Primalist#1"/>
	</Tree>
	<Items/>
	<Config/>
</LastEpochBuilding>]]
end

describe("game version 1.5", function()
	it("is loadable and offered as the latest version", function()
		assert.is_truthy(isValueInTable(treeVersionList, "1_5"))
		assert.is_truthy(isValueInTable(offeredTreeVersionList, "1_5"))
		assert.are.equal("1_5", latestTreeVersion)
		assert.are.equal("1_5", liveTargetVersion)
		assert.are.equal("1_5", legacyTargetVersion)
		assert.is_truthy(treeVersions["1_5"])
	end)

	it("loads the 1.5 bases and new uniques", function()
		local vd = data.versionData["1_5"]
		assert.is_truthy(vd)
		local helm = vd.itemBases["Pinnacle Helm"]
		assert.is_truthy(helm)
		assert.are.equal(0, helm.affixEffectModifier)
		assert.are.equal("Unsated Rage", vd.uniques[477].name)
		assert.are.equal("Withstand the Elements", vd.uniques[479].name)
		assert.are.equal(21, vd.uniques[477].baseTypeID)
		assert.are.equal(4, vd.uniques[479].baseTypeID)
	end)

	it("keeps the LETools display-only percent stat out of parsed stats", function()
		local tree = main:LoadTree("1_5")
		assert.is_truthy(tree)
		local node = tree.nodes["Primalist-0"]
		assert.is_truthy(node)
		assert.are.same({ "+1 Strength", "4% Increased Health Regeneration" }, node.stats)
		local temporal = tree.nodes["sr31hu-8"]
		assert.is_truthy(temporal)
		assert.are.same({ "+8 Void Damage" }, temporal.stats)
		assert.is_truthy(temporal.notScalingStats)
		assert.is_truthy(temporal.notScalingStats[1]:find("Damage Reduced By Increased Attack Speed", 1, true))
	end)

	it("includes the 1.5-only affixes and keeps the 1.4 rows", function()
		local mods = data.versionData["1_5"].itemMods.Item
		assert.are.equal("You have Berserking Rage", mods["1111_0"][1])
		assert.are.equal(
			"+1% Reduced Bonus Damage Taken from Critical Strikes per 4% Overcapped Physical Resistance",
			mods["1140_0"][1])
		assert.are.equal("+(4-6) Strength per Equipped Heretical Idol", mods["1150_0"][1])
		assert.are.equal("+1 to Summon Tide Elemental", mods["1153_0"][1])
		assert.is_nil(mods["1148_0"], "unique-specific affixes live in uniques_1_5, not ModItem")
		assert.are.equal("of Defense", mods["1_0"]["affix"], "1.4 rows must be preserved")
		local count = 0
		for _ in pairs(mods) do count = count + 1 end
		assert.is_true(count > 5907, "expected the 1.5 affix table to grow past 1.4")
	end)

	it("fills the implicit text for the new 1.5 bases", function()
		local bases = data.versionData["1_5"].itemBases
		assert.are.same(
			{ "+90 Melee Damage", "+(40-55) Spell Damage", "(40-46)% increased Melee Attack Speed" },
			bases["Axe Staff"].implicits)
		assert.are.same(
			{ "+40 Armor", "(12-16)% increased Movement Speed", "+1 Evade Charge" },
			bases["Icescale Greaves"].implicits)
		assert.are.same(
			{ "+38 Melee Damage", "+(38-45) Spell Damage", "(3-5)% less Echo Damage when a skill is Echoed" },
			bases["Warden Sceptre"].implicits)
		for _, name in ipairs({ "Axe Staff", "Icescale Greaves", "Warden Sceptre", "Icicle Bow" }) do
			for _, line in ipairs(bases[name].implicits) do
				assert.is_true(pcall(modLib.parseMod, line), name .. ": " .. line)
			end
		end
	end)

	it("formats the new 1.5 uniques without placeholder text", function()
		local uniques = data.versionData["1_5"].uniques
		assert.are.same({
			"(15-30)% increased Effect of Frenzy on You",
			"+(10-20)% Endurance",
			"{rounding:Integer}+(100-200) Endurance Threshold",
			"{rounding:Integer}+(4-8) Strength",
			"{rounding:Integer}+(4-8) Vitality",
		}, uniques[477].mods)
		assert.are.same({
			"(20-40)% Physical Resistance",
			"+(20-40)% Cold Resistance",
			"+(1-2) to Physical Skills",
			"+(1-2) to Cold Skills",
		}, uniques[479].mods)
		for id = 471, 488 do
			local unique = uniques[id]
			assert.is_truthy(unique, "unique " .. id .. " must load")
			for _, mod in ipairs(unique.mods) do
				assert.is_nil(mod:find("Dark Protection", 1, true), id .. ": " .. mod)
				assert.is_nil(mod:find("Level of Skills", 1, true), id .. ": " .. mod)
				assert.is_nil(mod:find("No Ward", 1, true), id .. ": " .. mod)
			end
		end
	end)

	it("loads the new 1.5 skill definitions", function()
		local dream = data.skills["Dreamslash"]
		assert.is_truthy(dream, "Dreamslash must be defined")
		assert.are.equal("dr4sl", dream.treeId)
		assert.are.equal(1.5, dream.stats.damageEffectiveness)
		assert.are.equal(2, dream.stats.melee_base_physical_damage)
		assert.are.equal("Rogue", dream.class)
		assert.are.equal("Bladedancer", dream.mastery)

		local lance = data.skills["Radiant Lance"]
		assert.is_truthy(lance, "Radiant Lance must be defined")
		assert.are.equal("ra1an", lance.treeId)
		assert.are.equal(5, lance.stats.damageEffectiveness)
		assert.are.equal(100, lance.stats.spell_base_lightning_damage)
		assert.are.equal("Sentinel", lance.class)
		assert.are.equal("Paladin", lance.mastery)
	end)

	it("computes the new 1.5 skills", function()
		newBuild()
		build.spec:SelectClass(4) -- Rogue
		build.characterLevelAutoMode = false
		build.characterLevel = 100
		build.itemsTab:CreateDisplayItemFromRaw([[Rarity: RARE
Poignard
Poignard]])
		build.itemsTab:AddDisplayItem()
		build.skillsTab:SelSkill(1, "Dreamslash")
		runCallback("OnFrame")
		assert.is_true((build.calcsTab.mainOutput.TotalDPS or 0) > 0, "Dreamslash must compute")

		newBuild()
		build.spec:SelectClass(2) -- Sentinel
		build.characterLevelAutoMode = false
		build.characterLevel = 100
		build.skillsTab:SelSkill(1, "Radiant Lance")
		runCallback("OnFrame")
		assert.is_true((build.calcsTab.mainOutput.TotalDPS or 0) > 0, "Radiant Lance must compute")
	end)

	it("has icons for the new 1.5 skill roots", function()
		local tree = main:LoadTree("1_5")
		for _, entry in ipairs({
			{ "dr4sl-0", "dreamslash-root" },
			{ "ra1an-0", "radiant_lance-root" },
			{ "su3lem-0", "summon_tide_elemental-root" },
		}) do
			local node = tree.nodes[entry[1]]
			assert.is_truthy(node, entry[1] .. " must exist")
			assert.are.equal(entry[2], node.icon)
			local f = io.open("TreeData/sprites/" .. entry[2] .. ".png", "rb")
			assert.is_truthy(f, entry[2] .. ".png must exist")
			f:close()
		end
	end)

	it("opens a 1.5 build and computes", function()
		loadBuildFromXML(buildXML(), "1_5-spec")
		assert.are.equal("1_5", build.spec.treeVersion)
		assert.are.equal(main.tree["1_5"], build.spec.tree)
		assert.is_true((build.calcsTab.mainOutput.FullDPS or 0) > 0)
	end)
end)
