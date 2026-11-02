-- First-class Variant affix slot (Last Epoch 1.5).
-- The game shows a separate orange "Variant" line on rings and gloves
-- (e.g. "+1 You have Runic Rage"), which does not consume a prefix/suffix.
local dkjson = require "dkjson"

describe("VariantAffix #variantAffix", function()
	it("is a distinct affix category in the 1.5 data", function()
		local mods = data.versionData["1_5"].itemMods.Item
		local runic = mods["1130_0"]
		assert.is_truthy(runic, "1130_0 must exist")
		assert.are.equal(7, runic.specialAffixType)
		assert.are.equal(44, runic.displayCategory)
		assert.are.equal("You have Runic Rage", runic["1"] or runic[1])
		assert.are.equal(0, runic.tier or 0) -- fixed variant roll; tier is cosmetic
	end)

	it("round-trips through BuildRaw/ParseRaw and colours as Variant", function()
		newBuild()
		local item = new("Item", "", "RARE")
		item.title = "Test Ring"
		item.baseName = "Opal Ring"
		item.crafted = true
		item.prefixes = {}
		item.suffixes = {}
		item.variantAffix = { modId = "1130_0", range = 128 }
		item:BuildAndParseRaw()

		local raw = item:BuildRaw()
		assert.is_not_nil(raw:find("Variant Affix: {range:128}1130_0", 1, true),
			"variant affix must round-trip into raw text")
		assert.is_truthy(item.variantAffix, "variant affix must parse back")
		assert.are.equal("1130_0", item.variantAffix.modId)
		assert.are.equal(128, item.variantAffix.range)
		local function active(list)
			local n = 0
			for _, affix in ipairs(list or {}) do
				if affix.modId and affix.modId ~= "None" then n = n + 1 end
			end
			return n
		end
		assert.are.equal(0, active(item.prefixes), "variant must not use a prefix slot")
		assert.are.equal(0, active(item.suffixes), "variant must not use a suffix slot")

		local variantLine
		for _, line in ipairs(item.explicitModLines) do
			if line.variantAffix then variantLine = line break end
		end
		assert.is_truthy(variantLine, "variant line must be in explicitModLines")
		assert.are.equal(7, variantLine.specialAffixType)
		local text = itemLib.formatModLine(variantLine, false, nil, item)
		assert.is_not_nil(text:find(colorCodes.VARIANT, 1, true),
			"variant line must use the orange Variant colour")
		assert.is_not_nil(text:find("You have Runic Rage", 1, true))
	end)

	it("routes a decoded save affix into variantAffix, not prefixes/suffixes", function()
		newBuild()
		local function affixBytes(affixId, tier, range)
			local hi = math.floor(affixId / 256)
			local lo = affixId % 256
			return tier * 16 + hi, lo, (range or 128)
		end
		local tb, ib, rb = affixBytes(1130, 0, 128)
		-- Minimal serialisation-v5 record: ring base (base 21 / subType 10).
		local d = { 5, 0, 0, 21, 10, 4, 128, 128, 128, 0, 0, 1, tb, ib, rb }
		local save = dkjson.encode({
			characterClass = 3,
			chosenMastery = 2,
			characterName = "VariantFixture",
			level = 100,
			savedCharacterTree = { nodeIDs = {}, nodePoints = {} },
			savedSkillTrees = {},
			savedQuests = {},
			savedItems = { { containerID = 9, data = d } },
		})
		local char = build.importTab:ReadJsonSaveData(save)
		local item
		for _, it in ipairs(char.items or {}) do
			if it.inventoryId == 9 then item = it break end
		end
		assert.is_truthy(item, "ring must import")
		assert.is_truthy(item.variantAffix, "variant affix must be routed to its own slot")
		assert.are.equal("1130_0", item.variantAffix.modId)
		assert.are.equal(0, #(item.prefixes or {}), "variant must not become a prefix")
		assert.are.equal(0, #(item.suffixes or {}), "variant must not become a suffix")
	end)
end)

describe("VariantAffix craft editor #variantAffix", function()
	it("offers Variant affixes for rings and rebuilds the slot", function()
		newBuild()
		build.itemsTab:CreateDisplayItemFromRaw([[Rarity: RARE
Opal Ring
Opal Ring]])
		local item = build.itemsTab.displayItem
		assert.is_truthy(item and item.base, "Opal Ring must load")
		local tab = build.itemsTab
		tab:CraftResetState()
		tab.craftEditItem = item
		tab.craftEditBaseEntry = { base = item.base, category = "basic" }
		tab:CraftRefreshAffixDropdowns()
		local offered = tab.craftAffixLists.variant or {}
		local hasRunic = false
		for _, entry in ipairs(offered) do
			if entry.statOrderKey == 1130 then hasRunic = true break end
		end
		assert.is_true(hasRunic, "Runic Rage (1130) must be offered on a ring")

		tab.craftAffixState.variant = { modKey = 1130, tier = 0, ranges = { 128 } }
		tab:CraftRebuildItem()
		assert.is_truthy(item.variantAffix, "craft rebuild must set variantAffix")
		assert.are.equal("1130_0", item.variantAffix.modId)
		local found
		for _, line in ipairs(item.explicitModLines) do
			if line.variantAffix then found = line break end
		end
		assert.is_truthy(found, "variant line must render first-class")
	end)
end)
