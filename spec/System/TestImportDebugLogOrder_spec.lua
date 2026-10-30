-- @leb-regression-guard: import-debug-log-preserves-parse-errors
-- ReadJsonSaveData emits [ITEM] no base match lines for skipped slots.
-- ImportItemsAndSkills used to call ResetDebugLog after parsing, erasing the
-- only diagnostic for a partial import (27/34 items on a 1.5 character).
-- The reset must happen before parsing, not after.

describe("ImportDebugLogOrder", function()
	local function readFile(path)
		local f = assert(io.open(path, "r"), "missing: " .. path)
		local s = f:read("*a")
		f:close()
		return s
	end

	local src = readFile("../src/Classes/ImportTab.lua")

	local function functionBody(name)
		local start = src:find("function ImportTabClass:" .. name .. "%(")
		assert.is_truthy(start, "function " .. name .. " not found")
		local stop = src:find("\nend\n", start, true)
		assert.is_truthy(stop, "end of function " .. name .. " not found")
		return src:sub(start, stop)
	end

	it("ImportItemsAndSkills no longer resets the log after parsing", function()
		local body = functionBody("ImportItemsAndSkills")
		assert.is_nil(body:find("ResetDebugLog", 1, true))
	end)

	it("DownloadFromMaxroll resets before ReadJsonSaveData", function()
		local body = functionBody("DownloadFromMaxroll")
		local resetAt = body:find("ResetDebugLog", 1, true)
		local parseAt = body:find("self:ReadJsonSaveData", 1, true)
		assert.is_truthy(resetAt and parseAt, "expected both calls")
		assert.is_true(resetAt < parseAt, "ResetDebugLog must precede ReadJsonSaveData")
	end)
end)
