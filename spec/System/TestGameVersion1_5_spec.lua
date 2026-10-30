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

	it("opens a 1.5 build and computes", function()
		loadBuildFromXML(buildXML(), "1_5-spec")
		assert.are.equal("1_5", build.spec.treeVersion)
		assert.are.equal(main.tree["1_5"], build.spec.tree)
		assert.is_true((build.calcsTab.mainOutput.FullDPS or 0) > 0)
	end)
end)
