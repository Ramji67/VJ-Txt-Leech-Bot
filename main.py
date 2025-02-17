from pyrogram import utils as pyroutils
pyroutils.MIN_CHAT_ID = -999999999999
pyroutils.MIN_CHANNEL_ID = -100999999999999
import pyromod
import os
import re
import sys
import json
import time
import asyncio
import requests
import subprocess
import logging
from utils import progress_bar
import core as helper
from vars import BOT_TOKEN, API_ID, API_HASH, MONGO_URI, BOT_NAME
import aiohttp
from aiohttp import ClientSession
from subprocess import getstatusoutput
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import StickerEmojiInvalid
from pyrogram.types.messages_and_media import message
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

import tempfile

from pytube import Playlist  #Youtube Playlist Extractor
from yt_dlp import YoutubeDL
import yt_dlp as youtube_dl

# Initialize bot
bot = Client("bot",
             bot_token=BOT_TOKEN,
             api_id=API_ID,
             api_hash=API_HASH)

# Get the MongoDB collection for this bot
collection = get_collection(BOT_NAME, MONGO_URI)
# Constants
OWNER_IDS = [5840594311]  # Replace with the actual owner user IDs

cookies_file_path ="modules/cookies.txt"
# Global variables
log_channel_id = [-1002323970081]
authorized_users = [5840594311,7856557198]
ALLOWED_CHANNEL_IDS = [-1002323970081]
my_name = "❤️"
overlay = None 
accept_logs = 0
bot_running = False
start_time = None
total_running_time = None
max_running_time = None
file_queue = []

# Load initial data from files
def load_initial_data():
    global log_channel_id, authorized_users, ALLOWED_CHANNEL_IDS, my_name, accept_logs
    global total_running_time, max_running_time
  
    log_channel_id = load_log_channel_id(collection)
    authorized_users = load_authorized_users(collection)
    ALLOWED_CHANNEL_IDS = load_allowed_channel_ids(collection)
    my_name = load_name(collection)
    accept_logs = load_accept_logs(collection)
    # Load bot running time and max running time
    total_running_time = load_bot_running_time(collection)
    max_running_time = load_max_running_time(collection)
    file_queue = load_queue_file(collection)

# Filters
def owner_filter(_, __, message):
    return bool(message.from_user and message.from_user.id in OWNER_IDS)

def channel_filter(_, __, message):
    return bool(message.chat and message.chat.id in ALLOWED_CHANNEL_IDS)

def auth_user_filter(_, __, message):
    return bool(message.from_user and message.from_user.id in authorized_users)

auth_or_owner_filter = filters.create(lambda _, __, m: auth_user_filter(_, __, m) or owner_filter(_, __, m))
auth_owner_channel_filter = filters.create(lambda _, __, m: auth_user_filter(_, __, m) or owner_filter(_, __, m) or channel_filter(_, __, m))
owner_or_channel_filter = filters.create(lambda _, __, m: owner_filter(_, __, m) or channel_filter(_, __, m))


#===================== Callback query handler ===============================

# Callback query handler for help button
@bot.on_callback_query(filters.regex("help") & auth_or_owner_filter)
async def help_callback(client: Client, query: CallbackQuery):
    await help_command(client, query.message)

@bot.on_callback_query(filters.regex("show_channels") & auth_or_owner_filter)
async def show_channels_callback(client: Client, query: CallbackQuery):
    await show_channels(client, query.message)

@bot.on_callback_query(filters.regex("remove_chat") & auth_or_owner_filter)
async def remove_chat_callback(client: Client, query: CallbackQuery):
    await remove_channel(client, query.message)

#====================== Command handlers ========================================
@bot.on_message(filters.command("add_log_channel") & filters.create(owner_filter))
async def add_log_channel(client: Client, message: Message):
    global log_channel_id
    try:
        new_log_channel_id = int(message.text.split(maxsplit=1)[1])
        log_channel_id = new_log_channel_id
        save_log_channel_id(collection, -1002323970081)
        await message.reply(f"Log channel ID updated to {new_log_channel_id}.")
    except (IndexError, ValueError):
        await message.reply("Please provide a valid channel ID.")

@bot.on_message(filters.command("auth_users") & filters.create(owner_filter))
async def show_auth_users(client: Client, message: Message):
    await message.reply(f"Authorized users: {authorized_users}")

@bot.on_message(filters.command("add_auth") & filters.create(owner_filter))
async def add_auth_user(client: Client, message: Message):
    global authorized_users
    try:
        new_user_id = int(message.text.split(maxsplit=1)[1])
        if new_user_id not in authorized_users:
            authorized_users.append(new_user_id)
            save_authorized_users(collection, authorized_users)
            await message.reply(f"User {new_user_id} added to authorized users.")
        else:
            await message.reply(f"User {new_user_id} is already in the authorized users list.")
    except (IndexError, ValueError):
        await message.reply("Please provide a valid user ID.")

@bot.on_message(filters.command("remove_auth") & filters.create(owner_filter))
async def remove_auth_user(client: Client, message: Message):
    global authorized_users
    try:
        user_to_remove = int(message.text.split(maxsplit=1)[1])
        if user_to_remove in authorized_users:
            authorized_users.remove(user_to_remove)
            save_authorized_users(collection, authorized_users)
            await message.reply(f"User {user_to_remove} removed from authorized users.")
        else:
            await message.reply(f"User {user_to_remove} is not in the authorized users list.")
    except (IndexError, ValueError):
        await message.reply("Please provide a valid user ID.")

@bot.on_message(filters.command("add_channel") & auth_or_owner_filter)
async def add_channel(client: Client, message: Message):
    global ALLOWED_CHANNEL_IDS
    try:
        new_channel_id = int(message.text.split(maxsplit=1)[1])
        if new_channel_id not in ALLOWED_CHANNEL_IDS:
            ALLOWED_CHANNEL_IDS.append(new_channel_id)
            save_allowed_channel_ids(collection, ALLOWED_CHANNEL_IDS)
            await message.reply(f"Channel {new_channel_id} added to allowed channels.")
        else:
            await message.reply(f"Channel {new_channel_id} is already in the allowed channels list.")
    except (IndexError, ValueError):
        await message.reply("Please provide a valid channel ID.")

@bot.on_message(filters.command("remove_channel") & auth_or_owner_filter)
async def remove_channel(client: Client, message: Message):
    global ALLOWED_CHANNEL_IDS
    try:
        channel_to_remove = int(message.text.split(maxsplit=1)[1])
        if channel_to_remove in ALLOWED_CHANNEL_IDS:
            ALLOWED_CHANNEL_IDS.remove(channel_to_remove)
            save_allowed_channel_ids(collection, ALLOWED_CHANNEL_IDS)
            await message.reply(f"Channel {channel_to_remove} removed from allowed channels.")
        else:
            await message.reply(f"Channel {channel_to_remove} is not in the allowed channels list.")
    except (IndexError, ValueError):
        await message.reply("Please provide a valid channel ID.")

@bot.on_message(filters.command("show_channels") & auth_or_owner_filter)
async def show_channels(client: Client, message: Message):
    if ALLOWED_CHANNEL_IDS:
        channels_list = "\n".join(map(str, ALLOWED_CHANNEL_IDS))
        await message.reply(f"Allowed channels:\n{channels_list}")
    else:
        await message.reply("No channels are currently allowed.")


# Add Chat Callback
@bot.on_callback_query(filters.regex("add_chat") & auth_or_owner_filter)
async def add_chat_callback(client: Client, query: CallbackQuery):
    await query.message.reply_text("Send me the Telegram post link of the channel where you want to use the bot:")
    input_msg = await client.listen(query.message.chat.id)
    await handle_add_chat(client, input_msg, query.message)

# Add Chat Command
@bot.on_message(filters.command("add_chat") & auth_or_owner_filter)
async def add_chat_command(client: Client, message: Message):
    await message.delete()
    editable = await message.reply_text("Send me the Telegram post link of the channel where you want to use the bot:")
    input_msg = await client.listen(editable.chat.id)
    await handle_add_chat(client, input_msg, editable)

# Handler to process the chat link
async def handle_add_chat(client: Client, input_msg: Message, original_msg: Message):
    global ALLOWED_CHANNEL_IDS

    url = input_msg.text
    await input_msg.delete()
    await original_msg.delete()

    # Extract chat ID from Telegram post link
    chat_id_match = re.search(r't\.me\/(?:c\/)?(\d+)', url)
    if chat_id_match:
        chat_id = chat_id_match.group(1)
        new_channel_id = int("-100" + chat_id)
    else:
        await original_msg.reply("Invalid Telegram post link.")
        return

    try:
        if new_channel_id not in ALLOWED_CHANNEL_IDS:
            ALLOWED_CHANNEL_IDS.append(new_channel_id)
            save_allowed_channel_ids(collection, ALLOWED_CHANNEL_IDS)
            await original_msg.reply(f"Channel {new_channel_id} added to allowed channels.")
        else:
            await original_msg.reply(f"Channel {new_channel_id} is already in the allowed channels list.")
    except (IndexError, ValueError) as e:
        await original_msg.reply(f"An error occurred while processing the channel ID: {str(e)}. Please try again.")

# Remove chat command handler
@bot.on_message(filters.command("remove_chat") & auth_or_owner_filter)
async def remove_channel(client: Client, message: Message):
    global ALLOWED_CHANNEL_IDS
    await message.delete()
    editable = await message.reply_text("Send Me The post link of The Channel to remove it from Allowed Channel List: ")
    input_msg = await client.listen(editable.chat.id)
    url = input_msg.text
    await input_msg.delete()
    await editable.delete()
    
    # Extract chat ID from Telegram post link
    chat_id_match = re.search(r't\.me\/(?:c\/)?(\d+)', url)
    if chat_id_match:
        chat_id = chat_id_match.group(1)
        channel_to_remove = int("-100" + chat_id)
    else:
        await message.reply("Invalid Telegram post link.")
        return
    
    try:
        if channel_to_remove in ALLOWED_CHANNEL_IDS:
            ALLOWED_CHANNEL_IDS.remove(channel_to_remove)
            save_allowed_channel_ids(collection, ALLOWED_CHANNEL_IDS)
            await message.reply(f"Channel {channel_to_remove} removed from allowed channels.")
        else:
            await message.reply(f"Channel {channel_to_remove} is not in the allowed channels list.")
    except (IndexError, ValueError):
        await message.reply("Please provide a valid channel ID.")

# Define the /watermark command handler
@bot.on_message(filters.command("watermark") & auth_or_owner_filter)
async def watermark_command(client: Client, message: Message):
    global overlay
    chat_id = message.chat.id
    editable = await message.reply("To set the Watermark upload an image or send `df` for default use")
    input_msg = await client.listen(chat_id)
    if input_msg.photo:
        overlay_path = await input_msg.download()
        if has_transparency(overlay_path):
            overlay = overlay_path
        else:
            overlay = await convert_to_png(overlay_path)
    if input_msg.document:
        document = input_msg.document
        if document.mime_type == "image/png":
            overlay_path = await input_msg.download(file_name=document.file_name)
            overlay = overlay_path
        else:
            await editable.edit("Please upload a .png file for the watermark.")
            await input_msg.delete()
            return    
    else:
        raw_text = input_msg.text
        if raw_text == "df":
            overlay = "watermark.png"
        elif raw_text.startswith("http://") or raw_text.startswith("https://"):
            getstatusoutput(f"wget '{raw_text}' -O 'raw_text.jpg'")
            overlay = "raw_text.jpg"
        else:
            overlay = None 
    await input_msg.delete()
    await editable.edit(f"Watermark set to: {overlay}")

# Function to check if an image has transparency
def has_transparency(image_path):
    # Implement logic to check for transparency
    # For example, using PIL library:
    from PIL import Image
    try:
        image = Image.open(image_path)
        if image.mode == "RGBA":
            return True
    except Exception as e:
        print(f"Error: {e}")
    return False

# Function to convert image to PNG format
async def convert_to_png(image_path):
    # Implement logic to convert image to PNG format
    # For example, using PIL library:
    from PIL import Image
    try:
        image = Image.open(image_path)
        # Create a new image with an alpha channel (transparency)
        new_image = Image.new("RGBA", image.size)
        new_image.paste(image, (0, 0), image)
        # Save the image as PNG
        png_path = image_path.replace(".jpg", ".png")
        new_image.save(png_path)
        return png_path
    except Exception as e:
        print(f"Error: {e}")
        return None

@bot.on_message(filters.command("logs") & filters.create(owner_filter))
async def send_logs(client: Client, message: Message):
    logs = get_last_two_minutes_logs()
    if logs:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_file:
            temp_file.write("".join(logs).encode('utf-8'))
            temp_file_path = temp_file.name
        
        await client.send_document(
            chat_id=message.chat.id,
            document=temp_file_path,
            file_name="Heroku_logs.txt"
        )
        os.remove(temp_file_path)
    else:
        await message.reply_text("No logs found for the last two minutes.")

@bot.on_message(filters.command("accept_logs") & filters.create(owner_filter))
async def accept_logs_command(client: Client, message: Message):
    global accept_logs
    chat_id = message.chat.id
    editable = await message.reply("Hey If You Want Accept The Logs send `df` Otherwise `no`")
    input_msg = await client.listen(chat_id)
    if input_msg.text.strip() == 'df':
        accept_logs = 1  
    else:
        accept_logs = 0
    save_accept_logs(collection, accept_logs)
    await input_msg.delete()
    await editable.edit(f"Accept logs set to: {accept_logs}")

@bot.on_message(filters.command("name") & auth_or_owner_filter)
async def set_name(client: Client, message: Message):
    global my_name
    try:
        my_name = message.text.split(maxsplit=1)[1]  # Extract the name from the message
        save_name(collection, my_name)  # Save the name to the database
        await message.reply(f"Name updated to {my_name}.")
    except IndexError:
        await message.reply("Please provide a name.")

#====================== START COMMAND ======================
class Data:
    START = (
        "🌟 𝗪𝗘𝗟𝗖𝗢𝗠𝗘 {0}! 🌟\n\n"
    )
# Define the start command handler
@bot.on_message(filters.command("start"))
async def start(client: Client, msg: Message):
    user = await client.get_me()
    mention = user.mention
    start_message = await client.send_message(
        msg.chat.id,
        Data.START.format(msg.from_user.mention)
    )

    await asyncio.sleep(1)
    await start_message.edit_text(
        Data.START.format(msg.from_user.mention) +
        "Initializing Uploader bot... 🤖\n\n"
        "Progress: [🤍🤍🤍🤍🤍🤍🤍🤍🤍🤍] 0%\n\n"
    )

    await asyncio.sleep(1)
    await start_message.edit_text(
        Data.START.format(msg.from_user.mention) +
        "Loading features... ⏳\n\n"
        "Progress: [🩵🩵🩵🤍🤍🤍🤍🤍🤍🤍] 25%\n\n"
    )
    
    await asyncio.sleep(1)
    await start_message.edit_text(
        Data.START.format(msg.from_user.mention) +
        "This may take a moment, sit back and relax! 😊\n\n"
        "Progress: [🩵🩵🩵🩵🩵🤍🤍🤍🤍🤍] 50%\n\n"
    )

    await asyncio.sleep(1)
    await start_message.edit_text(
        Data.START.format(msg.from_user.mention) +
        "Checking subscription status... 🔍\n\n"
        "Progress: [🩵🩵🩵🩵🩵🩵🩵🤍🤍🤍] 75%\n\n"
    )

    await asyncio.sleep(1)
    if msg.from_user.id in authorized_users:
        await start_message.edit_text(
            Data.START.format(msg.from_user.mention) +
            "Great!, You are a 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 member! 🌟 press `/help` in order to use me properly\n\n",
            reply_markup=help_button_keyboard
        )
    else:
        await asyncio.sleep(2)
        await start_message.edit_text(
            Data.START.format(msg.from_user.mention) +
            "You are currently using the 𝗙𝗥𝗘𝗘 version. 🆓\n\n"
            "I'm here to make your life easier by downloading videos from your **.txt** file 📄 and uploading them directly to Telegram!\n\n"
            "Want to get started? 𝗣𝗥𝗘𝗦𝗦 /id\n\n💬 Contact @Bhandara_2_O to get the 𝗦𝗨𝗕𝗦𝗖𝗥𝗜𝗣𝗧𝗜𝗢𝗡 🎫 and unlock the full potential of your new bot! 🔓"
        )


@bot.on_message(filters.command("stop"))
async def stop_handler(_, message):
    global bot_running, start_time
    if bot_running:
        bot_running = False
        start_time = None
        await message.reply_text("**𝗦𝗧𝗢𝗣𝗣𝗘𝗗**🚦", True)
        os.execl(sys.executable, sys.executable, *sys.argv)
    else:
        await message.reply_text("Bot is 𝗡𝗢𝗧 running.", True)


@bot.on_message(filters.command("check") & filters.create(owner_filter))
async def owner_command(bot: Client, message: Message):
    global OWNER_TEXT
    await message.reply_text(OWNER_TEXT)


# Help command handler
@bot.on_message(filters.command("help") & auth_owner_channel_filter)
async def help_command(client: Client, message: Message):
    await message.reply(help_text, reply_markup=keyboard)


#=================== TELEGRAM ID INFORMATION =============

@bot.on_message(filters.private & filters.command("info"))
async def info(bot: Client, update: Message):
    
    text = f"""--**Information**--

**🙋🏻‍♂️ First Name :** {update.from_user.first_name}
**🧖‍♂️ Your Second Name :** {update.from_user.last_name if update.from_user.last_name else 'None'}
**🧑🏻‍🎓 Your Username :** {update.from_user.username}
**🆔 Your Telegram ID :** {update.from_user.id}
**🔗 Your Profile Link :** {update.from_user.mention}"""
    
    await update.reply_text(        
        text=text,
        disable_web_page_preview=True,
        reply_markup=BUTTONS
    )


@bot.on_message(filters.private & filters.command("id"))
async def id(bot: Client, update: Message):
    if update.chat.type == "channel":
        await update.reply_text(
            text=f"**This Channel's ID:** {update.chat.id}",
            disable_web_page_preview=True
        )
    else:
        await update.reply_text(        
            text=f"**Your Telegram ID :** {update.from_user.id}",
            disable_web_page_preview=True,
            reply_markup=BUTTONS
        )  

    try:
        for i in range(count - 1, len(links)):

            V = links[i][1].replace("file/d/","uc?export=download&id=").replace("www.youtube-nocookie.com/embed", "youtu.be").replace("?modestbranding=1", "").replace("/view?usp=sharing","") # .replace("mpd","m3u8")
            url = "https://" + V

            if "visionias" in url:
                async with ClientSession() as session:
                    async with session.get(url, headers={'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9', 'Accept-Language': 'en-US,en;q=0.9', 'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'Pragma': 'no-cache', 'Referer': 'http://www.visionias.in/', 'Sec-Fetch-Dest': 'iframe', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'cross-site', 'Upgrade-Insecure-Requests': '1', 'User-Agent': 'Mozilla/5.0 (Linux; Android 12; RMX2121) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36', 'sec-ch-ua': '"Chromium";v="107", "Not=A?Brand";v="24"', 'sec-ch-ua-mobile': '?1', 'sec-ch-ua-platform': '"Android"',}) as resp:
                        text = await resp.text()
                        url = re.search(r"(https://.*?playlist.m3u8.*?)\"", text).group(1)

            elif 'videos.classplusapp' in url:
             url = requests.get(f'https://api.classplusapp.com/cams/uploader/video/jw-signed-url?url={url}', headers={'x-access-token': 'eyJjb3Vyc2VJZCI6IjQ1NjY4NyIsInR1dG9ySWQiOm51bGwsIm9yZ0lkIjo0ODA2MTksImNhdGVnb3J5SWQiOm51bGx9'}).json()['url']

            elif "tencdn.classplusapp" in url or "media-cdn-alisg.classplusapp.com" in url or "videos.classplusapp" in url or "media-cdn.classplusapp" in url:
             headers = {'Host': 'api.classplusapp.com', 'x-access-token': 'eyJjb3Vyc2VJZCI6IjQ1NjY4NyIsInR1dG9ySWQiOm51bGwsIm9yZ0lkIjo0ODA2MTksImNhdGVnb3J5SWQiOm51bGx9', 'user-agent': 'Mobile-Android', 'app-version': '1.4.37.1', 'api-version': '18', 'device-id': '5d0d17ac8b3c9f51', 'device-details': '2848b866799971ca_2848b8667a33216c_SDK-30', 'accept-encoding': 'gzip'}
             params = (('url', f'{url}'),)
             response = requests.get('https://api.classplusapp.com/cams/uploader/video/jw-signed-url', headers=headers, params=params)
             url = response.json()['url']
            
            elif '/utkarshapp.mpd' in url:                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               
             id =  url.split("/")[-2]                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               
             url =  "https://apps-s3-prod.utkarshapp.com/" + id + "/utkarshapp.com"
           
            elif '/master.mpd' in url:
             id =  url.split("/")[-2]
             url =  f"https://madxapi-d0cbf6ac738c.herokuapp.com/{id}/master.m3u8?token={raw_text4}"

            name1 = links[i][0].replace("\t", "").replace(":", "").replace("/", "").replace("+", "").replace("#", "").replace("|", "").replace("@", "").replace("*", "").replace(".", "").replace("https", "").replace("http", "").strip()
            name = f'{str(count).zfill(3)}) {name1[:60]}'

            if "youtu" in url:
                ytf = f"b[height<={raw_text2}][ext=mp4]/bv[height<={raw_text2}][ext=mp4]+ba[ext=m4a]/b[ext=mp4]"
            else:
                ytf = f"b[height<={raw_text2}]/bv[height<={raw_text2}]+ba/b/bv+ba"

            if "jw-prod" in url:
                cmd = f'yt-dlp -o "{name}.mp4" "{url}"'
           
            if "apps-s3-jw-prod.utkarshapp" in url:                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               
                cmd = f'yt-dlp -o "{name}.mp4" "{url}"'      
       
            elif "webvideos.classplusapp." in url:
               cmd = f'yt-dlp --add-header "referer:https://web.classplusapp.com/" --add-header "x-cdn-tag:empty" -f "{ytf}" "{url}" -o "{name}.mp4"'
            
            else:
                cmd = f'yt-dlp -f "{ytf}" "{url}" -o "{name}.mp4"'
            try:  
                
                cc = f'**[📽️] 𝗩𝗶𝗱_𝗜𝗱 :** {str(count).zfill(3)}.**\n\n\n**☘️𝗧𝗶𝘁𝗹𝗲 𝗡𝗮𝗺𝗲** ➤ {name1}.({res}).𝔗𝔲𝔰𝔥𝔞𝔯.mkv**\n\n\n**<pre><code>📚𝗕𝗮𝘁𝗰𝗵 𝗡𝗮𝗺𝗲** ➤ **{raw_text0}</code></pre>**\n\n\n**📥 𝗘𝘅𝘁𝗿𝗮𝗰𝘁𝗲𝗱 𝗕𝘆** ➤ **{raw_text3}**' 
                cc1 = f'**[📁] 𝗣𝗱𝗳_𝗜𝗱 :** {str(count).zfill(3)}.**\n\n\n**☘️𝗧𝗶𝘁𝗹𝗲 𝗡𝗮𝗺𝗲** ➤ {name1}.𝔗𝔲𝔰𝔥𝔞𝔯.pdf**\n\n\n**<pre><code>📚𝗕𝗮𝘁𝗰𝗵 𝗡𝗮𝗺𝗲** ➤ **{raw_text0}</code></pre>**\n\n\n**📥 𝗘𝘅𝘁𝗿𝗮𝗰𝘁𝗲𝗱 𝗕𝘆** ➤ **{raw_text3}**'
                if "drive" in url:
                    try:
                        ka = await helper.download(url, name)
                        copy = await bot.send_document(chat_id=m.chat.id,document=ka, caption=cc1)
                        count+=1
                        os.remove(ka)
                        time.sleep(1)
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        time.sleep(e.x) 
                        continue
                
                elif ".pdf" in url:
                    try:
                        cmd = f'yt-dlp -o "{name}.pdf" "{url}"'
                        download_cmd = f"{cmd} -R 25 --fragment-retries 25"
                        os.system(download_cmd)
                        copy = await bot.send_document(chat_id=m.chat.id, document=f'{name}.pdf', caption=cc1)
                        count += 1
                        os.remove(f'{name}.pdf')
                    except FloodWait as e:
                        await m.reply_text(str(e))
                        time.sleep(e.x)
                        continue
                else:
                    Show = f"**🛎️𝗗𝗢𝗪𝗡𝗟𝗢𝗔𝗗𝗜𝗡𝗚🛎️**\n\n**📝ɴᴀᴍᴇ » **`{name}\n\n❄ǫᴜᴀʟɪᴛʏ » {raw_text2}`\n\n**🔗ᴜʀʟ »** `{url}`\n\n🤖𝗕𝗢𝗧 𝗠𝗔𝗗𝗘 𝗕𝗬 ➤ 𝗧𝗨𝗦𝗛𝗔𝗥"
                    prog = await m.reply_text(Show)
                    res_file = await helper.download_video(url, cmd, name)
                    filename = res_file
                    await prog.delete(True)
                    await helper.send_vid(bot, m, cc, filename, thumb, name, prog)
                    count += 1
                    time.sleep(1)

            except Exception as e:
                await m.reply_text(
                    f"**🥺ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ғᴀɪʟᴇᴅ🥺 **\n{str(e)}\n**ɴᴀᴍᴇ** » {name}\n**ʟɪɴᴋ** » `{url}`"
                )
                continue

    except Exception as e:
        await m.reply_text(e)
    await m.reply_text("**🥳✅𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆 𝗗𝗼𝗻𝗲✅🥳**")


bot.run()
