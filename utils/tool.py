import json, sys, os

from utils.database import (
    get_config, update_config,
    get_antinuke_status, update_antinuke_status,
    get_module_status, update_module_status,
    get_logs_channel, update_logs_channel,
    get_threshold, update_threshold
)

def getConfig(guild_id):
    return get_config(str(guild_id))

def updateConfig(guild_id, data):
    update_config(str(guild_id), data)

def getanti(guild_id):
    return get_antinuke_status(str(guild_id))

def updateanti(guild_id, data):
    update_antinuke_status(str(guild_id), data)

def getantiban(guild_id):
    return get_module_status(str(guild_id), 'antiban')

def updateantiban(guild_id, data):
    update_module_status(str(guild_id), 'antiban', data)

def getantibot(guild_id):
    return get_module_status(str(guild_id), 'antibot')

def updateantibot(guild_id, data):
    update_module_status(str(guild_id), 'antibot', data)

def getantichannel(guild_id):
    return get_module_status(str(guild_id), 'antichannel')

def updateantichannel(guild_id, data):
    update_module_status(str(guild_id), 'antichannel', data)

def getantiemoji(guild_id):
    return get_module_status(str(guild_id), 'antiemoji')

def updateantiemoji(guild_id, data):
    update_module_status(str(guild_id), 'antiemoji', data)

def getantiguild(guild_id):
    return get_module_status(str(guild_id), 'antiguild')

def updateantiguild(guild_id, data):
    update_module_status(str(guild_id), 'antiguild', data)

def getantikick(guild_id):
    return get_module_status(str(guild_id), 'antikick')

def updateantikick(guild_id, data):
    update_module_status(str(guild_id), 'antikick', data)

def getantiping(guild_id):
    return get_module_status(str(guild_id), 'antiping')

def updateantiping(guild_id, data):
    update_module_status(str(guild_id), 'antiping', data)

def getantiprune(guild_id):
    return get_module_status(str(guild_id), 'antiprune')

def updateantiprune(guild_id, data):
    update_module_status(str(guild_id), 'antiprune', data)

def getantirole(guild_id):
    return get_module_status(str(guild_id), 'antirole')

def updateantirole(guild_id, data):
    update_module_status(str(guild_id), 'antirole', data)

def getantiweb(guild_id):
    return get_module_status(str(guild_id), 'antiweb')

def updateantiweb(guild_id, data):
    update_module_status(str(guild_id), 'antiweb', data)

def getantimember(guild_id):
    return get_module_status(str(guild_id), 'antimember')

def antiupdatememb(guild_id, data):
    update_module_status(str(guild_id), 'antimember', data)

def getAntiChannelLogs(guild_id):
    return {'channel': get_logs_channel(str(guild_id), 'channel')}

def updateAntiChannelLogs(guild_id, channel_id):
    update_logs_channel(str(guild_id), 'channel', channel_id)

def getAntiModLogs(guild_id):
    return {'channel': get_logs_channel(str(guild_id), 'mod')}

def updateAntiModLogs(guild_id, channel_id):
    update_logs_channel(str(guild_id), 'mod', channel_id)

def getAntiGuildLogs(guild_id):
    return {'channel': get_logs_channel(str(guild_id), 'guild')}

def updateAntiGuildLogs(guild_id, channel_id):
    update_logs_channel(str(guild_id), 'guild', channel_id)

def getAntiRoleLogs(guild_id):
    return {'channel': get_logs_channel(str(guild_id), 'role')}

def updateAntiRoleLogs(guild_id, channel_id):
    update_logs_channel(str(guild_id), 'role', channel_id)

def getAntiChannelThreshold(guild_id):
    return get_threshold(str(guild_id), 'channel')