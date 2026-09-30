import os
import json
import asyncio
import threading
import requests
import discord
from discord.ui import Button, View
from flask import Flask
from groq import Groq

# --- Dummy Web Server for Render 24/7 Keep-Alive ---
app = Flask('')

@app.route('/')
def home():
    return "Ultra-Fast Minecraft Groq Bot is active!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()
# ---------------------------------------------------

# Environment Variables
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
GODLIKE_PANEL_URL = "https://panel.godlike.host"
GODLIKE_API_KEY = os.getenv("GODLIKE_API_KEY", "").strip()
SERVER_ID = os.getenv("SERVER_ID", "").strip()
MY_DISCORD_ID = int(os.getenv("MY_DISCORD_ID", "0"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

# Fallback models in case one is unavailable
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "llama3-70b-8192",
    "mixtral-8x7b-32768"
]

# Memory File Path
MEMORY_FILE = "memory.json"

# --- Persistent Long-Term Memory Helpers ---
def load_memory() -> dict:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"rules": [], "notes": []}
    return {"rules": [], "notes": []}

def save_memory_fact(fact_or_rule: str) -> str:
    data = load_memory()
    if fact_or_rule not in data["rules"]:
        data["rules"].append(fact_or_rule)
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return f"Memory updated: Saved '{fact_or_rule}' into persistent memory."
    return "Rule is already saved in memory."

def get_saved_memory() -> str:
    data = load_memory()
    rules = data.get("rules", [])
    if not rules:
        return "No specific long-term rules saved yet."
    return "Saved Server Rules & Notes:\n" + "\n".join([f"- {r}" for r in rules])

# --- Godlike Panel API Headers ---
def get_api_headers(content_type="application/json"):
    return {
        "Authorization": f"Bearer {GODLIKE_API_KEY}",
        "Content-Type": content_type,
        "Accept": "application/json"
    }

# --- Safe / Non-Destructive Server Tools ---
def get_server_resources() -> str:
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/resources"
    try:
        res = requests.get(url, headers=get_api_headers())
        if res.status_code == 200:
            data = res.json()['attributes']
            stats = data['resources']
            state = data['current_state']
            ram_mb = round(stats['memory_bytes'] / (1024 * 1024), 2)
            cpu_pct = round(stats['cpu_absolute'], 2)
            disk_mb = round(stats['disk_bytes'] / (1024 * 1024), 2)
            return f"📊 **Server Status:** `{state.upper()}`\n💻 **CPU:** `{cpu_pct}%` | 🧠 **RAM:** `{ram_mb} MB` | 💾 **Disk:** `{disk_mb} MB`"
        return f"Failed to fetch resources. Status Code: {res.status_code}"
    except Exception as e:
        return f"API Error: {str(e)}"

def get_online_players() -> str:
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/command"
    try:
        res = requests.post(url, headers=get_api_headers(), json={"command": "list"})
        if res.status_code == 204:
            return "Sent '/list' command to server console. Check logs for response."
        return f"Failed to send list command. Status Code: {res.status_code}"
    except Exception as e:
        return f"API Error: {str(e)}"

def send_console_command(command: str) -> str:
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/command"
    try:
        res = requests.post(url, headers=get_api_headers(), json={"command": command})
        if res.status_code == 204:
            return f"Command `{command}` executed successfully on console."
        return f"Failed to execute command. Status: {res.status_code}, Response: {res.text}"
    except Exception as e:
        return f"API Error: {str(e)}"

def read_server_file(file_path: str) -> str:
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/contents?file={file_path}"
    headers = {"Authorization": f"Bearer {GODLIKE_API_KEY}", "Accept": "text/plain"}
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            return res.text
        return f"Failed to read file '{file_path}'. Status Code: {res.status_code}"
    except Exception as e:
        return f"Error reading file: {str(e)}"

def write_server_file(file_path: str, content: str) -> str:
    if not content or len(content.strip()) == 0:
        return "Error: Cannot write empty content to file."
        
    existing = read_server_file(file_path)
    if existing and not existing.startswith("Failed to read"):
        backup_url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/write?file={file_path}.bak"
        requests.post(backup_url, headers=get_api_headers("text/plain"), data=existing)

    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/write?file={file_path}"
    try:
        res = requests.post(url, headers=get_api_headers("text/plain"), data=content)
        if res.status_code == 204:
            return f"File '{file_path}' written successfully. (Auto-backup created at '{file_path}.bak')"
        return f"Failed to write file. Status: {res.status_code}, Response: {res.text}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

def list_server_files(directory: str = "") -> str:
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/list?directory={directory}"
    try:
        res = requests.get(url, headers=get_api_headers())
        if res.status_code == 200:
            items = [item['attributes']['name'] for item in res.json().get('data', [])]
            return f"Files in '{directory or 'root'}': " + ", ".join(items)
        return f"Failed to list directory. Status Code: {res.status_code}"
    except Exception as e:
        return f"Error listing directory: {str(e)}"

def read_latest_logs() -> str:
    log_content = read_server_file("logs/latest.log")
    if log_content.startswith("Failed to read"):
        return log_content
    lines = log_content.strip().split("\n")
    return "Last 50 lines of logs:\n" + "\n".join(lines[-50:])

def execute_power_signal(signal: str) -> str:
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/power"
    try:
        res = requests.post(url, headers=get_api_headers(), json={"signal": signal})
        if res.status_code == 204:
            return f"Power signal '{signal.upper()}' sent successfully to server."
        return f"Failed power action. Status Code: {res.status_code}"
    except Exception as e:
        return f"Error executing power action: {str(e)}"

def execute_file_deletion(file_path: str) -> str:
    url = f"{GODLIKE_PANEL_URL}/api/client/servers/{SERVER_ID}/files/delete"
    payload = {"root": "/", "files": [file_path]}
    try:
        res = requests.post(url, headers=get_api_headers(), json=payload)
        if res.status_code == 204:
            return f"File '{file_path}' deleted successfully."
        return f"Failed file deletion. Status Code: {res.status_code}"
    except Exception as e:
        return f"Error deleting file: {str(e)}"

# Groq Tools Schema
groq_tools = [
    {
        "type": "function",
        "function": {
            "name": "get_server_resources",
            "description": "Fetches real-time server status (CPU, RAM, Disk, Online state)."
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_online_players",
            "description": "Checks online players on the Minecraft server using console list command."
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_console_command",
            "description": "Executes a console command on the Minecraft server.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The command to run, e.g. 'op player'"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_server_file",
            "description": "Reads content of a specified server file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to file, e.g. 'plugins/Essentials/config.yml'"}
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_server_file",
            "description": "Safely updates/writes content to a file after creating a .bak backup.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Relative path to file"},
                    "content": {"type": "string", "description": "Full file content to write"}
                },
                "required": ["file_path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_server_files",
            "description": "Lists files/folders in a specified server directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directory path, e.g. 'plugins'"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_latest_logs",
            "description": "Fetches the last 50 lines of logs/latest.log."
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory_fact",
            "description": "Saves long-term instructions or rules given by the user to memory.json.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact_or_rule": {"type": "string", "description": "Rule or fact to remember"}
                },
                "required": ["fact_or_rule"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_saved_memory",
            "description": "Returns saved long-term memories and rules."
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_power_signal",
            "description": "Sends power state signal (start, stop, restart, kill) to server.",
            "parameters": {
                "type": "object",
                "properties": {
                    "signal": {"type": "string", "description": "power signal e.g. 'restart'"}
                },
                "required": ["signal"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_file_deletion",
            "description": "Deletes a file or directory from server.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to delete"}
                },
                "required": ["file_path"]
            }
        }
    }
]

# --- Confirmation View for Owner Approval ---
class ConfirmationView(View):
    def __init__(self, owner_id: int, action_type: str, action_data: str):
        super().__init__(timeout=60)
        self.owner_id = owner_id
        self.action_type = action_type
        self.action_data = action_data

    @discord.ui.button(label="✅ অনুমোদন দিন", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ কেবল অনার এই কাজের অনুমোদন দিতে পারবেন!", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="⏳ **অনুমোদন দেওয়া হয়েছে। কাজ সম্পন্ন হচ্ছে...**", view=self)

        if self.action_type == "power":
            res = execute_power_signal(self.action_data)
            await interaction.followup.send(f"⚡ **সার্ভার অ্যাকশন রিপোর্ট:** {res}")
        elif self.action_type == "delete":
            res = execute_file_deletion(self.action_data)
            await interaction.followup.send(f"🗑 **ফাইল ডিলিট রিপোর্ট:** {res}")

    @discord.ui.button(label="❌ বাতিল করুন", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ কেবল অনার এই বাটন ব্যবহার করতে পারবেন!", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="🛑 **কাজটি বাতিল করা হয়েছে।**", view=self)

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}!")
    print("Groq Ultra-Fast AI Assistant is online!")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if MY_DISCORD_ID != 0 and message.author.id != MY_DISCORD_ID:
        return

    msg_text = message.content.strip()

    async with message.channel.typing():
        recent_history = []
        async for msg in message.channel.history(limit=4):
            recent_history.append(f"{msg.author.name}: {msg.content}")
        recent_history.reverse()
        chat_context = "\n".join(recent_history)

        saved_rules = get_saved_memory()

        sys_instruction = (
            "You are an extraordinarily smart Minecraft Paper 1.21.11 server administrator powered by Groq AI.\n"
            f"Long-Term Saved Memory:\n{saved_rules}\n\n"
            "Operational Guidelines:\n"
            "1. When editing or writing files, ensure complete YAML syntax without missing lines.\n"
            "2. ONLY invoke power signals or file deletions if the user explicitly orders you to restart, stop, or delete RIGHT NOW.\n"
            "3. Be extremely precise, helpful, and natural."
        )

        try:
            client = Groq(api_key=GROQ_API_KEY)
            
            messages = [
                {"role": "system", "content": sys_instruction},
                {"role": "user", "content": f"Context:\n{chat_context}\n\nUser Message: {msg_text}"}
            ]

            response = None
            last_err = None

            # Try models dynamically until one succeeds
            for model_name in GROQ_MODELS:
                try:
                    def sync_groq(m_name):
                        return client.chat.completions.create(
                            model=m_name,
                            messages=messages,
                            tools=groq_tools,
                            tool_choice="auto"
                        )
                    response = await asyncio.to_thread(sync_groq, model_name)
                    break
                except Exception as e:
                    last_err = e
                    continue

            if not response:
                raise last_err if last_err else RuntimeError("All Groq models failed.")

            msg_obj = response.choices[0].message

            if msg_obj.tool_calls:
                for tool_call in msg_obj.tool_calls:
                    fn_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}

                    if fn_name == "execute_power_signal":
                        signal = args.get("signal", "restart")
                        view = ConfirmationView(MY_DISCORD_ID, "power", signal)
                        await message.channel.send(
                            f"⚠️ **অনুমোদনের অনুরোধ:** এআই সার্ভারটি `{signal.upper()}` করতে চাচ্ছে। আপনি কি অনুমোদন দিচ্ছেন?",
                            view=view
                        )

                    elif fn_name == "execute_file_deletion":
                        path = args.get("file_path", "")
                        view = ConfirmationView(MY_DISCORD_ID, "delete", path)
                        await message.channel.send(
                            f"⚠️️ **অনুমোদনের অনুরোধ:** এআই `{path}` ফাইলটি মুছে ফেলতে চাচ্ছে। আপনি কি অনুমোদন দিচ্ছেন?",
                            view=view
                        )

                    elif fn_name == "get_server_resources":
                        res = get_server_resources()
                        await message.channel.send(res)

                    elif fn_name == "get_online_players":
                        res = get_online_players()
                        await message.channel.send(f"👥 **প্লেয়ার লিস্ট স্ট্যাটাস:** {res}")

                    elif fn_name == "send_console_command":
                        cmd = args.get("command")
                        res = send_console_command(cmd)
                        await message.channel.send(f"⚙️ **Console Executed:** `{cmd}`\n📄 **Result:** {res}")

                    elif fn_name == "write_server_file":
                        path = args.get("file_path")
                        content = args.get("content")
                        res = write_server_file(path, content)
                        await message.channel.send(f"📝 **File Saved:** `{path}`\n📄 **Result:** {res}")

                    elif fn_name == "read_server_file":
                        path = args.get("file_path")
                        res = read_server_file(path)
                        if len(res) > 1900:
                            res = res[:1900] + "\n...(truncated)"
                        await message.channel.send(f"📖 **File Content (`{path}`):**\n```yaml\n{res}\n```")

                    elif fn_name == "list_server_files":
                        directory = args.get("directory", "")
                        res = list_server_files(directory)
                        await message.channel.send(f"📁 **Directory List:**\n{res}")

                    elif fn_name == "read_latest_logs":
                        res = read_latest_logs()
                        if len(res) > 1900:
                            res = res[-1900:]
                        await message.channel.send(f"📋 **Server Logs:**\n```log\n{res}\n```")

                    elif fn_name == "save_memory_fact":
                        fact = args.get("fact_or_rule")
                        res = save_memory_fact(fact)
                        await message.channel.send(f"🧠 **মেমোরি সেভ করা হয়েছে:** {res}")

                    elif fn_name == "get_saved_memory":
                        res = get_saved_memory()
                        await message.channel.send(f"📜 **সংরক্ষিত মেমোরি নিয়মাবলি:**\n{res}")

            elif msg_obj.content:
                res_text = msg_obj.content
                if len(res_text) > 1900:
                    for i in range(0, len(res_text), 1900):
                        await message.channel.send(res_text[i:i+1900])
                else:
                    await message.channel.send(res_text)

        except Exception as err:
            await message.channel.send(f"❌ **Error details:** `{str(err)[:1800]}`")

if __name__ == "__main__":
    keep_alive()
    bot.run(DISCORD_BOT_TOKEN)
        
