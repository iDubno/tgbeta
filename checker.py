import os
import uuid
import asyncio
import aiohttp
import aiofiles
from pyrogram import Client, enums, filters, types
import ssl
import logging
from datetime import datetime, timedelta, timezone
import nest_asyncio
import speedtest
import subprocess
import signal

# Configuration and Constants
API_ID = "Enter Value Here"
API_HASH = "Enter  Value Here"
BOT_TOKEN = "Enter Value Here"
CHAT_ID = -1001341570295
APP_CENTER_URL = "https://api.appcenter.ms/v0.1/public/sdk/apps/f9726602-67c9-48d2-b5d0-4761f1c1a8f3/releases/latest"
THUMBNAIL_URL = "https://graph.org/file/b8895c429c91ac72b542d.png"
THUMBNAIL_PATH = "thumb.jpg"
DOWNLOAD_URL = "https://install.appcenter.ms/users/drklo-2kb-ghpo/apps/telegram-beta-2/distribution_groups/all-users-of-telegram-beta-2"

sslcontext = ssl.create_default_context()
sslcontext.check_hostname = False
sslcontext.verify_mode = ssl.CERT_NONE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AUTHORIZED_USERS = [1019823976, 1743735915, 1218619440]

async def download_file(session, url, message, total_size, file_path, retries=3):
    for attempt in range(retries):
        try:
            async with session.get(url, ssl=sslcontext) as response:
                response.raise_for_status()
                downloaded_size = 0
                last_update_time = asyncio.get_event_loop().time()
                
                async with aiofiles.open(file_path, 'wb') as file:
                    async for chunk in response.content.iter_chunked(8192):
                        await file.write(chunk)
                        downloaded_size += len(chunk)
                        current_time = asyncio.get_event_loop().time()
                        if message and current_time - last_update_time >= 2:  # Update every 2 seconds
                            percentage = (downloaded_size / total_size) * 100
                            await message.edit_text(
                                f"**Build {short_version} ({version}) was released.**\n"
                                f"__Downloading... {downloaded_size / 1024 / 1024:.2f} MB of {total_size / 1024 / 1024:.2f} MB ({percentage:.2f}%)__"
                            )
                            last_update_time = current_time
                
                if message:
                    await message.edit_text(
                        f"**Build {short_version} ({version}) was released.**\n"
                        f"__Downloaded {total_size / 1024 / 1024:.2f} MB (100%)__"
                    )
                
                return file_path
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                raise

async def fetch_release_info(session):
    async with session.get(APP_CENTER_URL) as response:
        response.raise_for_status()
        return await response.json()

async def prepare_thumbnail(session):
    if not os.path.exists(THUMBNAIL_PATH):
        await download_file(session, THUMBNAIL_URL, None, 0, THUMBNAIL_PATH)

async def check_for_updates(first_run=False):
    unique_session_id = str(uuid.uuid4())
    app = Client(unique_session_id, api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    
    previous_version = "00000"
    
    conn = aiohttp.TCPConnector(limit_per_host=10, ssl=sslcontext)
    async with aiohttp.ClientSession(connector=conn) as session:
        await prepare_thumbnail(session)
        print(f"Using chat ID in check_for_updates: {CHAT_ID}")

        while True:
            try:
                release_info = await fetch_release_info(session)
                
                global version, short_version
                version = os.getenv('INPUT_VERSION', release_info.get('version'))
                short_version = os.getenv('INPUT_SHORT_VERSION', release_info.get('short_version'))
                download_url = os.getenv('INPUT_DOWNLOAD_URL', release_info['download_url'])
                release_notes = os.getenv('INPUT_RELEASE_NOTES', release_info['release_notes'])
                total_size = release_info['size']
                uploaded_at = release_info.get('uploaded_at', 'not found')

                if uploaded_at != 'not found':
                    uploaded_at_dt = datetime.strptime(uploaded_at, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)

                if first_run:
                    first_run = False
                    if uploaded_at != 'not found' and uploaded_at_dt >= datetime.now(timezone.utc) - timedelta(days=1):
                        if version != previous_version:
                            async with app:
                                if download_url == 'not found':
                                    await app.send_message(CHAT_ID, "⚠ Warning! New release with no download URL found. Recommend investigation.")
                                else:
                                    message = await app.send_photo(CHAT_ID, photo=THUMBNAIL_URL, caption=f"**Build {short_version} ({version}) was released.**\n__Preparing to download...__")
                                    apk_path = "app.apk"
                                    file_path = await download_file(session, download_url, message, total_size, apk_path)
                                    await app.send_chat_action(CHAT_ID, enums.ChatAction.UPLOAD_DOCUMENT)
                                    caption = f"🚀 **New Beta v{short_version} ({version}) released!**\n\n"
                                    caption += f"📝 Release notes:\n{release_notes}"
                                    await app.send_document(CHAT_ID, file_path, caption=caption, thumb=THUMBNAIL_PATH)
                                    await message.delete()
                                    os.remove(apk_path)
                                
                                previous_version = version
                
            except Exception as e:
                logger.error(f"An error occurred: {e}")
            
            await asyncio.sleep(3)

async def send_latest_build(app, session):
    release_info = await fetch_release_info(session)
    
    global version, short_version
    version = os.getenv('INPUT_VERSION', release_info.get('version'))
    short_version = os.getenv('INPUT_SHORT_VERSION', release_info.get('short_version'))
    download_url = os.getenv('INPUT_DOWNLOAD_URL', release_info['download_url'])
    release_notes = os.getenv('INPUT_RELEASE_NOTES', release_info['release_notes'])
    total_size = release_info['size']
    uploaded_at = release_info.get('uploaded_at', 'not found')

    if uploaded_at != 'not found':
        uploaded_at_dt = datetime.strptime(uploaded_at, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)

    if download_url == 'not found':
        await app.send_message(CHAT_ID, "⚠ Warning! New release with no download URL found. Recommend investigation.")
    else:
        print(f"Using chat ID in send_latest_build: {CHAT_ID}")
        message = await app.send_photo(CHAT_ID, photo=THUMBNAIL_URL, caption=f"**Build {short_version} ({version}) was released.**\n__Preparing to download...__")
        apk_path = "app.apk"
        file_path = await download_file(session, download_url, message, total_size, apk_path)
        await app.send_chat_action(CHAT_ID, enums.ChatAction.UPLOAD_DOCUMENT)
        caption = f"🚀 **New Beta v{short_version} ({version}) released!**\n\n"
        caption += f"📝 Release notes:\n{release_notes}"
        await app.send_document(CHAT_ID, file_path, caption=caption, thumb=THUMBNAIL_PATH)
        await message.delete()
        os.remove(apk_path)

async def start_bot():
    unique_session_id = str(uuid.uuid4())
    app = Client(unique_session_id, api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

    conn = aiohttp.TCPConnector(limit_per_host=10, ssl=sslcontext)
    session = aiohttp.ClientSession(connector=conn)

    @app.on_message(filters.command("latest", prefixes="."))
    async def latest_build(client, message):
        print(f"Using chat ID in latest_build: {CHAT_ID}")
        m = await message.reply_text("`Loading...`")
        try:
            release_info = await fetch_release_info(session)
            version = os.getenv('INPUT_VERSION', release_info.get('version'))
            short_version = os.getenv('INPUT_SHORT_VERSION', release_info.get('short_version'))
            total_size = release_info['size']
            release_notes = os.getenv('INPUT_RELEASE_NOTES', release_info['release_notes'])
            uploaded_at = release_info.get('uploaded_at', 'not found')

            if uploaded_at != 'not found':
                uploaded_at_dt = datetime.strptime(uploaded_at, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
                uploaded_at_str = uploaded_at_dt.strftime("%B %d, %Y at %H:%M:%S UTC")
            else:
                uploaded_at_str = 'not found'

            response_message = (
                f"**Latest Build:**\n"
                f"🛠️ Version: {short_version} ({version})\n\n"
                f"💾 File Size: {total_size / 1024 / 1024:.2f} MB\n\n"
                f"⏰ Uploaded at: {uploaded_at_str}\n\n"
                f"📝 Release Notes:\n{release_notes}"
            )

            reply_markup = types.InlineKeyboardMarkup(
                [
                    [types.InlineKeyboardButton("Download", url=DOWNLOAD_URL)]
                ]
            )

            await m.edit_text(response_message, reply_markup=reply_markup)
        except Exception as e:
            await m.edit_text(f"**Error:** {e}")

    @app.on_message(filters.command("connectiontest", prefixes="."))
    async def connectiontest_command(client, message):
        print(f"Using chat ID in connectiontest_command: {CHAT_ID}")
        if message.from_user.id not in AUTHORIZED_USERS:
            await message.reply_text("**You are not authorized to use this command.**")
            return

        m = await message.reply_text("`Running speed test...`")
        try:
            st = speedtest.Speedtest()
            st.download()
            st.upload()
            results = st.results.dict()

            download_speed = results["download"] / 1_000_000  # Convert to Mbps
            upload_speed = results["upload"] / 1_000_000  # Convert to Mbps

            response_message = (
                f"**Connection Test Results:**\n"
                f"📥 Download Speed: {download_speed:.2f} Mbps\n"
                f"📤 Upload Speed: {upload_speed:.2f} Mbps"
            )
            await m.edit_text(response_message)
        except Exception as e:
            await m.edit_text(f"**Error:** {e}")

    @app.on_message(filters.command("speedtest", prefixes="."))
    async def speedtest_command(client, message):
        print(f"Using chat ID in speedtest_command: {CHAT_ID}")
        if message.from_user.id not in AUTHORIZED_USERS:
            await message.reply_text("**You are not authorized to use this command.**")
            return

        await send_latest_build(client, session)

    @app.on_message(filters.command("eval", prefixes="."))
    async def eval_command(client, message):
        print(f"Using chat ID in eval_command: {CHAT_ID}")
        if message.from_user.id not in AUTHORIZED_USERS:
            await message.reply_text("**You are not authorized to use this command.**")
            return

        command = message.text.split(maxsplit=1)[1]  # Get the command after .eval
        m = await message.reply_text("`Processing...`")
        
        async def run_command():
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                preexec_fn=os.setsid
            )

            stdout_buffer = []
            stderr_buffer = []
            last_update_time = asyncio.get_event_loop().time()

            async def read_stream(stream, buffer):
                nonlocal last_update_time
                while True:
                    line = await stream.readline()
                    if line:
                        buffer.append(line.decode())
                        current_time = asyncio.get_event_loop().time()
                        if current_time - last_update_time >= 5:  # Update every 5 seconds
                            try:
                                await m.edit_text(f"**Command Output:**\n```\n{''.join(stdout_buffer + stderr_buffer)}\n```")
                            except Exception as e:
                                if "FloodWait" in str(e):
                                    await asyncio.sleep(int(str(e).split()[1]))
                                elif "MESSAGE_NOT_MODIFIED" not in str(e):
                                    raise
                                elif "MESSAGE_TOO_LONG" in str(e):
                                    await m.edit_text("**Output is too long.**")
                                    return
                            last_update_time = current_time
                    else:
                        break

            try:
                await asyncio.wait_for(asyncio.gather(
                    read_stream(proc.stdout, stdout_buffer),
                    read_stream(proc.stderr, stderr_buffer)
                ), timeout=60)
            except asyncio.TimeoutError:
                os.killpg(os.getpgid(proc.pid), signal.SIGINT)
                stdout, stderr = await proc.communicate()
                stdout_buffer.append(stdout.decode())
                stderr_buffer.append(stderr.decode())

            await proc.wait()
            return ''.join(stdout_buffer + stderr_buffer)

        output = await run_command()

        if len(output) > 4096:
            await m.edit_text("**Output too long.**")
        else:
            if len(output) == 0:
                output = "Command executed successfully with no output."
            await m.edit_text(f"**Command Output:**\n```\n{output}\n```")

    await app.start()
    await prepare_thumbnail(session)
    await check_for_updates(first_run=True)

    await app.idle()
    await session.close()

if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(start_bot())
