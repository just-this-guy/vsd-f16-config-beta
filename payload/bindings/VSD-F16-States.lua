-- Original additive telemetry hook for the F-16 cycling VSD buttons.
-- Existing export hooks are chained. No commands are accepted by this script.
local socket = require("socket")
local udp = socket.udp()
udp:settimeout(0)
local previousActivity = LuaExportActivityNextEvent
local previousStop = LuaExportStop
local arguments = {159,449,455,457,510,528,531,532,533,534,536,555,556,559,564,566,567,572,670,671,672,673,675,676,677,678,679,680,681,693,710,715,716,717,718,719,720,721,722,723,728}
LuaExportActivityNextEvent = function(t)
    local nextTime = t + 0.1
    if previousActivity then
        local other = previousActivity(t)
        if type(other) == "number" and other > t then nextTime = math.min(nextTime, other) end
    end
    local self = LoGetSelfData()
    if self and self.Name == "F-16C_50" then
        local device = GetDevice(0)
        if device then
            local values = {"F16", string.format("%.3f", LoGetModelTime())}
            for _, arg in ipairs(arguments) do
                values[#values+1] = tostring(arg) .. "=" .. string.format("%.3f", device:get_argument_value(arg))
            end
            udp:sendto(table.concat(values, "|"), "127.0.0.1", 26028)
        end
    end
    return nextTime
end
LuaExportStop = function()
    if previousStop then previousStop() end
    -- Keep socket open: DCS can start another mission without reloading Export.lua.
end
