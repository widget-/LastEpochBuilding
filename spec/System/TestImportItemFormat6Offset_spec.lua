-- @leb-regression-guard: import-item-format-6-base-offset
-- 1.5 character saves carry item data with a four-byte seed (d[1] == 6), so
-- the baseTypeID/subTypeID pair is at d[6],d[7]. Formats 3/5 use d[4],d[5]
-- and format 2 uses d[2],d[3]; all other item fields are relative to the same
-- offset. Reading format 6 with the old d[4] offset matched no bases and
-- produced a single misidentified item with no mods.

local dkjson = require "dkjson"

local function makeItemData(format, baseTypeID, subTypeID)
	local d = {}
	for i = 1, 32 do
		d[i] = 0
	end
	d[1] = format
	local base = (format == 2) and 2 or (format == 6) and 6 or 4
	d[base] = baseTypeID
	d[base + 1] = subTypeID
	d[base + 2] = 1 -- normal rarity, avoids the unique/affix path
	return d
end

local function makeSave(items)
	return {
		characterClass = 4,
		chosenMastery = 2,
		characterName = "Format6Fixture",
		level = 99,
		cycle = 8,
		savedCharacterTree = { nodeIDs = {}, nodePoints = {} },
		savedQuests = {},
		savedSkillTrees = {},
		savedItems = items,
	}
end

describe("ImportItemFormat6Offset", function()
	it("reads a format-6 base pair from d[6],d[7]", function()
		newBuild()
		local char = build.importTab:ReadJsonSaveData(dkjson.encode(makeSave({
			{ containerID = 2, formatVersion = 2, data = makeItemData(6, 0, 49) },
		})))
		assert.equals(1, #char.items)
		assert.equals("Pinnacle Helm", char.items[1].baseName)
	end)

	it("still reads a format-5 base pair from d[4],d[5]", function()
		newBuild()
		local char = build.importTab:ReadJsonSaveData(dkjson.encode(makeSave({
			{ containerID = 2, formatVersion = 2, data = makeItemData(5, 0, 43) },
		})))
		assert.equals(1, #char.items)
		assert.equals("Leather Mask", char.items[1].baseName)
	end)

	it("detects the format-6 idol altar from d[6],d[7]", function()
		newBuild()
		local char = build.importTab:ReadJsonSaveData(dkjson.encode(makeSave({
			{ containerID = 123, formatVersion = 2, data = makeItemData(6, 41, 11) },
		})))
		assert.equals("Pyramidal Altar", char.altarName)
	end)
end)
