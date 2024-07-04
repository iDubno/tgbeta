# This is now the main and only file. The other files are for the GitHub Actions configuration, which we do not use anymore.
# We run this code on a server, so some values will be empty. 
import os
import asyncio
import aiohttp
import aiofiles
from pyrogram import Client, enums
import ssl
import logging
from datetime import datetime
import nest_asyncio

# Configuration and Constants
API_ID = "Enter Value Here"
API_HASH = "Enter Value Here"
BOT_TOKEN = "Enter Value Here"
CHAT_ID = -1001961065542
APP_CENTER_URL = "https://api.appcenter.ms/v0.1/public/sdk/apps/f9726602-67c9-48d2-b5d0-4761f1c1a8f3/releases/latest"
THUMBNAIL_URL = "https://graph.org/file/b8895c429c91ac72b542d.png"
THUMBNAIL_PATH = "thumb.jpg"

sslcontext = ssl.create_default_context()
sslcontext.check_hostname = False
sslcontext.verify_mode = ssl.CERT_NONE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

async def check_for_updates():
    app = Client("telegram_beta", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
    
    previous_version = "00000"
    
    conn = aiohttp.TCPConnector(limit_per_host=10, ssl=sslcontext)
    async with aiohttp.ClientSession(connector=conn) as session:
        await prepare_thumbnail(session)

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
                    uploaded_at_dt = datetime.strptime(uploaded_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                    uploaded_at_str = uploaded_at_dt.strftime("%B %d, %Y at %H:%M:%S UTC")
                else:
                    uploaded_at_str = 'not found'

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
                            caption += f"⏰ Uploaded at: {uploaded_at_str}\n\n"
                            caption += f"📝 Release notes:\n{release_notes}"
                            await app.send_document(CHAT_ID, file_path, caption=caption, thumb=THUMBNAIL_PATH)
                            await message.delete()
                            os.remove(apk_path)
                        
                        previous_version = version
            
            except Exception as e:
                logger.error(f"An error occurred: {e}")
            
            await asyncio.sleep(3)

if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(check_for_updates())
