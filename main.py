import os
import threading
import requests
import discord
import asyncio
from flask import Flask
from google import genai
from google.genai import types

# --- Dummy Web Server for Render Free Tier ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()
# ---------------------------------------------

# Configuration (Environment Variables)
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
GODLIKE_PANEL_URL = "https://panel.godlike.host"
GODLIKE_API_KEY = os.getenv("GODLIKE_API_KEY", "")
SERVER_ID = os.getenv("SERVER_ID", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

MY_DISCORD_ID = int(os.getenv("MY_DISCORD_ID", "0"))

# Initialize Gemini Client
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# Tool 1: Console Command Function
def send_console_command(command: str) -> str:
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/command"
    headers = {
        "Authorization": f"Bearer {GODLIKE_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {"command": command}
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 204:
        return f"Command '{command}' executed successfully on Minecraft console."
    else:
        return f"Failed to execute command. Status: {response.status_code}, Error: {response.text}"

# Tool 2: File Write / Edit Function
def write_server_file(file_path: str, content: str) -> str:
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/write?file={file_path}"
    headers = {
        "Authorization": f"Bearer {GODLIKE_API_KEY}",
        "Content-Type": "text/plain",
        "Accept": "application/json"
    }
    response = requests.post(url, headers=headers, data=content)
    if response.status_code == 204:
        return f"File '{file_path}' written/updated successfully."
    else:
        return f"Failed to write file. Status: {response.status_code}, Error: {response.text}"

# Tool 3: File Read Function
def read_server_file(file_path: str) -> str:
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/contents?file={file_path}"
    headers = {
        "Authorization": f"Bearer {GODLIKE_API_KEY}",
        "Accept": "text/plain"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        return f"Failed to read file '{file_path}'. Status: {response.status_code}"

# Discord Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}!")
    print("Gemini Minecraft Server Manager is online and active 24/7!")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if MY_DISCORD_ID != 0 and message.author.id != MY_DISCORD_ID:
        return

    async with message.channel.typing():
        sys_instruction = (
            "You are an expert Minecraft server administrator assistant inside Discord. "
            "When asked to run a console command, read a file, or write/edit a config/file on the Godlike Minecraft server, "
            "always call the provided tools (`send_console_command`, `write_server_file`, `read_server_file`). "
            "Be precise with Minecraft config syntax (e.g. server.properties, plugin YAML files)."
        )

        # Automatic Retry System for 503 / High Demand Errors
        max_retries = 3
        response = None
        
        for attempt in range(max_retries):
            try:
                response = gemini_client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=message.content,
                    config=types.GenerateContentConfig(
                        system_instruction=sys_instruction,
                        tools=[send_console_command, write_server_file, read_server_file],
                    )
                )
                break  # Successful response, exit loop
            except Exception as err:
                # 503 or UNAVAILABLE occurs: wait 3 seconds and retry
                if ("503" in str(err) or "UNAVAILABLE" in str(err)) and attempt < max_retries - 1:
                    await asyncio.sleep(3)
                    continue
                else:
                    await message.channel.send(f"❌ Error processing request: {str(err)}")
                    return

        try:
            if response and response.function_calls:
                for call in response.function_calls:
                    if call.name == "send_console_command":
                        cmd = call.args.get("command")
                        res = send_console_command(cmd)
                        await message.channel.send(f"⚙️ **Executed Console Command:** `{cmd}`\n📄 **Result:** {res}")
                        
                    elif call.name == "write_server_file":
                        path = call.args.get("file_path")
                        content = call.args.get("content")
                        res = write_server_file(path, content)
                        await message.channel.send(f"📝 **File Updated:** `{path}`\n📄 **Result:** {res}")
                        
                    elif call.name == "read_server_file":
                        path = call.args.get("file_path")
                        res = read_server_file(path)
                        if len(res) > 1900:
                            res = res[:1900] + "\n...(truncated due to length)"
                        await message.channel.send(f"📖 **File Content (`{path}`):**\n```\n{res}\n```")

            elif response and response.text:
                await message.channel.send(response.text)

        except Exception as e:
            await message.channel.send(f"❌ Error processing response: {str(e)}")

if __name__ == "__main__":
    keep_alive()
    bot.run(DISCORD_BOT_TOKEN)
                                             
