-- Last Epoch 1.5 Blood Rage variants. Ground truth:
-- Properties.Property_Ability_bloodRageFrenzy_*_AltText in the game i18n.
describe("BloodRageVariants #modParser", function()
	local function find(mods, name, typ)
		for _, m in ipairs(mods) do
			if m.name == name and m.type == typ then return m end
		end
	end

	it("Sanguine Rage grants bleed chance, DoT damage, and the common Blood Rage buff", function()
		local mods, extra = modLib.parseMod("You have Sanguine Rage")
		assert.is_nil(extra, "the line must parse completely")
		local bleed = find(mods, "BleedChance", "BASE")
		assert.is_truthy(bleed, "BleedChance BASE must exist")
		assert.are.equal(200, bleed.value)
		assert.are.equal(ModFlag.Hit, bleed.flags)
		local dot = find(mods, "Damage", "INC")
		assert.is_truthy(dot, "Damage INC must exist")
		assert.are.equal(100, dot.value)
		assert.are.equal(ModFlag.Dot, dot.flags)
		local hasAttack, hasCast = false, false
		for _, m in ipairs(mods) do
			if m.name == "Speed" and m.type == "INC" then
				if bit.band(m.flags, ModFlag.Attack) ~= 0 then hasAttack = true end
				if bit.band(m.flags, ModFlag.Cast) ~= 0 then hasCast = true end
			end
		end
		assert.is_true(hasAttack, "attack speed share")
		assert.is_true(hasCast, "cast speed share")
		local mv = find(mods, "MovementSpeed", "INC")
		assert.is_truthy(mv)
		assert.are.equal(3, mv.value)
	end)

	it("every Rage line gets the common buff without residue", function()
		for _, name in ipairs({ "Berserking", "Predator", "Murderous", "Runic", "Pack" }) do
			local line = "You have " .. name .. " Rage"
			local mods, extra = modLib.parseMod(line)
			assert.is_nil(extra, line .. " must parse completely")
			assert.is_truthy(find(mods, "Speed", "INC"), line .. " must grant attack/cast speed")
			assert.is_truthy(find(mods, "MovementSpeed", "INC"), line .. " must grant movement speed")
		end
	end)

	it("Empowered Rage grants +10 to all attributes", function()
		local mods, extra = modLib.parseMod("You have Empowered Rage")
		assert.is_nil(extra)
		for _, attr in ipairs({ "Str", "Dex", "Int", "Att" }) do
			local m = find(mods, attr, "BASE")
			assert.is_truthy(m, attr .. " must be granted")
			assert.are.equal(10, m.value)
		end
	end)

	it("overcapped physical resistance gloves scale from the overcap stat", function()
		local mods, extra = modLib.parseMod("+1% Increased Attack Speed per 5% Overcapped Physical Resistance")
		assert.is_nil(extra)
		local speed = find(mods, "Speed", "INC")
		assert.is_truthy(speed)
		assert.are.equal(1, speed.value)
		local tag = speed[1]
		assert.is_truthy(tag and tag.type == "PerStat")
		assert.are.equal("PhysicalResistOverCap", tag.stat)
		assert.are.equal(5, tag.div)

		local critMods, critExtra = modLib.parseMod("+1% Reduced Bonus Damage Taken from Critical Strikes per 4% Overcapped Physical Resistance")
		assert.is_nil(critExtra)
		local crit = find(critMods, "ReduceCritExtraDamage", "BASE")
		assert.is_truthy(crit)
		assert.are.equal(4, crit[1].div)
	end)
end)

describe("BloodRageVariants build import #modParser", function()
	it("Widget_hs2 Sanguine ring carries the mapped mods, not residue", function()
		local f = assert(io.open("Builds/Widget_hs2.xml", "r"))
		local xml = f:read("*a"); f:close()
		loadBuildFromXML(xml, "Widget_hs2")

		local ring, line
		for _, item in pairs(build.itemsTab.items) do
			for _, ml in ipairs(item.explicitModLines or {}) do
				if ml.line == "You have Sanguine Rage" then ring, line = item, ml break end
			end
		end
		assert.is_truthy(ring, "Sanguine ring must load")
		assert.is_nil(line.extra, "rage line must parse completely")

		local bleed, dot
		for _, m in ipairs(ring.modList or {}) do
			if m.name == "BleedChance" and m.type == "BASE" then bleed = m end
			if m.name == "Damage" and m.type == "INC" and m.flags == ModFlag.Dot then dot = m end
		end
		assert.is_truthy(bleed, "Sanguine must grant +200% bleed chance")
		assert.are.equal(200, bleed.value)
		assert.is_truthy(dot, "Sanguine must grant 100% increased DoT damage")
		assert.are.equal(100, dot.value)
	end)
end)
