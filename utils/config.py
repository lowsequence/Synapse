import os
import json

with open("info.json", "r") as f:
    config_data = json.load(f)

TOKEN = config_data.get("TOKEN", "")
No_Prefix = config_data.get("np", [])
NAME = config_data.get("BotName", "Synapse")
server = config_data.get("serverLink", "")
ch = "https://discord.com/channels/699587669059174461/1271825678710476911"
OWNER_IDS = config_data.get("OWNER_IDS", [])
BotName = config_data.get("BotName", "Synapse")
serverLink = config_data.get("serverLink", "")
whCL = config_data.get("wh_cl", "")
whBL = config_data.get("wh_bl", "")
statusText = config_data.get("statusText", ".help"),
np_webhook = config_data.get("np_webhook", "")