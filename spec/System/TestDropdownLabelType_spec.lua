-- @leb-regression-guard: dropdown-label-type
-- A dropdown list entry may be a table without a usable `label` (e.g. a socket
-- group whose displayLabel has not been calculated yet after unallocate/undo).
-- Returning the table to DrawString throws "expected string, got table" every
-- frame and takes the whole UI down. GetListLabel must always return a string.

describe("DropdownLabelType", function()
	local dd = new("DropDownControl", nil, 0, 0, 100, 20, {}, function() end)

	it("returns a plain string unchanged", function()
		assert.equals("Alpha", dd:GetListLabel("Alpha"))
	end)

	it("uses a string label from a table", function()
		assert.equals("Beta", dd:GetListLabel({ label = "Beta" }))
	end)

	it("falls back to name when label is missing", function()
		assert.equals("Gamma", dd:GetListLabel({ name = "Gamma" }))
	end)

	it("falls back to name when label is not a string", function()
		assert.equals("Delta", dd:GetListLabel({ label = {}, name = "Delta" }))
	end)

	it("returns an empty string for an unlabeled table", function()
		assert.equals("", dd:GetListLabel({}))
	end)

	it("stringifies numbers", function()
		assert.equals("5", dd:GetListLabel(5))
	end)

	it("returns an empty string for nil", function()
		assert.equals("", dd:GetListLabel(nil))
	end)
end)
