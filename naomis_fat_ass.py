import discord
from discord.ext import commands
from datetime import datetime, timezone
import re
import os
from dotenv import load_dotenv

load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix="!", intents=intents)

DEFAULT_VERIFICATION_CHANNEL = "state-ya-business"

@bot.event
async def on_ready():
    print(f"Bot is ready. Logged in as {bot.user}.")
    try:
        synced = await bot.tree.sync()  
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")

async def send_long_message(interaction, content, max_length=2000):
    chunks = []
    current_chunk = ""
    
    for line in content.splitlines(keepends=True):
        if len(current_chunk) + len(line) > max_length:
            chunks.append(current_chunk)
            current_chunk = ""
        current_chunk += line

    if current_chunk:
        chunks.append(current_chunk)

    for chunk in chunks:
        await interaction.followup.send(chunk)

@bot.tree.command(name="check_verifications", description="Check for users with multiple messages containing date patterns")
async def check_verifications(
    interaction: discord.Interaction,
    before: str = None,
    after: str = None,
    only_inconsistent: bool = False,
    user_id: str = None,
    channel_name: str = DEFAULT_VERIFICATION_CHANNEL
):
    await interaction.response.defer()

    verification_channel = discord.utils.get(interaction.guild.channels, name=channel_name)
    
    if not verification_channel:
        await interaction.followup.send(f"Verification channel '{channel_name}' not found.")
        return

    before_date = datetime.strptime(before, "%m-%d-%Y").replace(tzinfo=timezone.utc) if before else None
    after_date = datetime.strptime(after, "%m-%d-%Y").replace(tzinfo=timezone.utc) if after else None

    date_pattern = re.compile(r"\b(\d{1,4}[/-]\d{1,2}[/-]\d{1,4})\b")
    mention_pattern = re.compile(r"<@!?(\d+)>")

    user_messages = {}

    last_message = None
    while True:
        batch_empty = True
        async for message in verification_channel.history(limit=1000, before=last_message):
            batch_empty = False
            if user_id and str(message.author.id) != user_id:
                continue  

            if message.author.name == "Deleted User" or not hasattr(message.author, "name"):
                continue  

            message_date = message.created_at

            if after_date and message_date < after_date:
                break

            if before_date and message_date > before_date:
                continue

            user = message.author
            if user not in user_messages:
                user_messages[user] = []
            
            clean_content = mention_pattern.sub("@user", message.content)
            if message.embeds:
                for embed in message.embeds:
                    clean_content += f"\n[Embed content omitted]"

            user_messages[user].append(clean_content)
            last_message = message

        if batch_empty or (after_date and message_date < after_date):
            break

    response = ""
    for user, messages in user_messages.items():
        if len(messages) < 2:
            continue

        dates_found = []
        for msg in messages:
            dates = date_pattern.findall(msg)
            if dates:
                dates_found.extend(dates)
        
        if dates_found:
            consistent = all(date == dates_found[0] for date in dates_found)
            if only_inconsistent and consistent:
                continue 

            status_emoji = "✅" if consistent else "❌"
            response += f"{status_emoji} **{user.name}** (`{user.id}`): **{len(messages)} messages**\n"
            for idx, msg in enumerate(messages, 1):
                response += f"    `{idx})` {msg}\n"
            response += "\n"

    if response:
        await send_long_message(interaction, response)
    else:
        if only_inconsistent:
            await interaction.followup.send("No users with inconsistent date patterns found.")
        else:
            await interaction.followup.send("No users with 2 or more messages containing date patterns found within the specified date range.")

bot.run(DISCORD_BOT_TOKEN)
