import asyncio
import discord
import os
import random
import requests
import json
import datetime
import io
import spotipy
from discord.ext import commands
from discord.utils import get
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv
from PIL import Image
from spotipy import SpotifyClientCredentials
from youtube_dl import YoutubeDL

# Load environment variables
load_dotenv()

# Discord API credentials
DISCORD_TOKEN = 'APIkey'

# Enable intents
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# DeviantArt API credentials
DEVIANTART_API_KEY = os.getenv('APIkey')
DEVIANTART_API_URL = 'https://www.deviantart.com/api/v1/oauth2/browse/popular'

# Stable Diffusion API credentials
STABLEDIFFUSION_API_KEY = os.getenv('APIkey')
STABLEDIFFUSION_API_URL = 'https://api.stablediffusion.com/v1/generate'

# Google Calendar API credentials
SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = os.path.join(os.getcwd(), 'AccountFile')
creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build('calendar', 'v3', credentials=creds)

# Spotify API credentials
SPOTIPY_CLIENT_ID = 'ClientID'
SPOTIPY_CLIENT_SECRET = 'ClientKey'
SPOTIPY_REDIRECT_URI = 'RedirectURL'


# Voice class with is_connected, move_to, is_playing, and is_paused methods
class Voice:
    def __init__(self, bot):
        self.bot = bot
        self.voice_client = None

    def is_connected(self):
        return self.voice_client and self.voice_client.is_connected()

    async def move_to(self, channel):
        if self.is_connected():
            await self.voice_client.move_to(channel)
        else:
            self.voice_client = await channel.connect()

    def is_playing(self):
        return self.voice_client and self.voice_client.is_playing()

    def is_paused(self):
        return self.voice_client and self.voice_client.is_paused()


# Autorole function
@bot.event
async def on_member_join(member):
    role = get(member.guild.roles, name='Member')
    await member.add_roles(role)


# DeviantArt search function
@bot.command(name='deviantart', help='Search for an image on DeviantArt')
async def deviantart_search(ctx, *args):
    query = ' '.join(args)
    headers = {'Authorization': f'Bearer {DEVIANTART_API_KEY}'}
    params = {'q': query, 'limit': 1}
    response = requests.get(DEVIANTART_API_URL, headers=headers, params=params)
    if response.status_code == 200:
        data = json.loads(response.text)
        if data['has_more']:
            await ctx.send('More than one result found. Please refine your search.')
        elif data['results']:
            result = data['results'][0]
            await ctx.send(result['url'])
        else:
            await ctx.send('No results found.')
    else:
        await ctx.send('Error searching for image.')


# Dice rolling function
@bot.command(name='roll', help='Roll any form of dice')
async def roll_dice(ctx, dice: str):
    try:
        rolls, limit = map(int, dice.split('d'))
    except Exception:
        await ctx.send(
            'Invalid format. Please use the format NdM, where N is the number of dice and M is the number of sides on '
            'each die.')
        return
    result = ', '.join(str(random.randint(1, limit)) for r in range(rolls))
    await ctx.send(result)


# Function to generate an image using Stable Diffusion AI
async def generate_image():
    headers = {'Authorization': f'Bearer {STABLEDIFFUSION_API_KEY}'}
    data = {'model': 'your_model_name_here'}
    response = requests.post(STABLEDIFFUSION_API_URL, headers=headers, json=data)
    image_bytes = response.content
    image = Image.open(io.BytesIO(image_bytes))
    return image


# Function to create a Discord event from a Google Calendar event
def create_discord_event(event):
    start = event['start'].get('dateTime', event['start'].get('date'))
    end = event['end'].get('dateTime', event['end'].get('date'))
    start_time = datetime.datetime.fromisoformat(start).strftime('%m/%d/%Y %I:%M %p')
    end_time = datetime.datetime.fromisoformat(end).strftime('%m/%d/%Y %I:%M %p')
    description = event['description'] if 'description' in event else ''
    location = event['location'] if 'location' in event else ''
    return f"**{event['summary']}**\n{start_time} - {end_time}\n{description}\n{location}"


# Function to get upcoming Google Calendar events
def get_upcoming_events():
    events_result = service.events().list(calendarId='primary', timeMin=datetime.datetime.utcnow().isoformat() + 'Z',maxResults=10, singleEvents=True, orderBy='startTime').execute()
    events = events_result.get('items', [])
    return events


# Spotify track search function
@bot.command(name='spotify', help='Search for a track on Spotify')
async def spotify_search(ctx, *args):
    query = ' '.join(args)
    sp = spotipy.Spotify(
        auth_manager=SpotifyClientCredentials(client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET))
    results = sp.search(q=query, type='track', limit=1)
    if results['tracks']['items']:
        track = results['tracks']['items'][0]
        artists = ', '.join([artist['name'] for artist in track['artists']])
        album = track['album']['name']
        image_url = track['album']['images'][0]['url']
        preview_url = track['preview_url']
        embed = discord.Embed(title=track['name'], description=f'by {artists} from the album {album}', color=0x1DB954)
        embed.set_thumbnail(url=image_url)
        embed.add_field(name='Preview', value=preview_url, inline=False)
        await ctx.send(embed=embed)
    else:
        await ctx.send('No results found.')


# Discord bot command to play a song
@bot.command(name='play', help='Play a song in a voice channel')
async def play(ctx, *args):
    query = ' '.join(args)
    voice = Voice(bot)
    voice_channel = ctx.author.voice.channel
    if not voice_channel:
        await ctx.send('You need to be in a voice channel to use this command.')
        return
    await voice.move_to(voice_channel)
    ydl_opts = {'format': 'bestaudio', 'noplaylist': 'True'}
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f'ytsearch:{query}', download=False)['entries'][0]
        url = info['url']
        title = info['title']
        await ctx.send(f'Playing {title}')
        voice.voice_client.play(discord.FFmpegPCMAudio(url), after=lambda e: print(f'Error: {e}') if e else None)


# Discord bot command to pause the current song
@bot.command(name='pause', help='Pause the current song')
async def pause(ctx):
    voice = Voice(bot)
    if voice.is_playing():
        voice.voice_client.pause()
        await ctx.send('Song paused.')
    else:
        await ctx.send('No song is currently playing.')


# Discord bot command to resume the current song
@bot.command(name='resume', help='Resume the current song')
async def resume(ctx):
    voice = Voice(bot)
    if voice.is_paused():
        voice.voice_client.resume()
        await ctx.send('Song resumed.')
    else:
        await ctx.send('No song is currently paused.')


# Discord bot command to stop the current song
@bot.command(name='stop', help='Stop the current song')
async def stop(ctx):
    voice = Voice(bot)
    if voice.is_playing() or voice.is_paused():
        voice.voice_client.stop()
        await ctx.send('Song stopped.')
    else:
        await ctx.send('No song is currently playing.')


# Discord bot command to generate an image
@bot.command(name='generate_image', help='Generate an image using Stable Diffusion AI')
async def generate_image_command(ctx):
    image = await generate_image()
    with io.BytesIO() as image_binary:
        image.save(image_binary, 'PNG')
        image_binary.seek(0)
        await ctx.send(file=discord.File(fp=image_binary, filename='image.png'))


# Discord bot command to get upcoming events
@bot.command(name='upcoming_events', help='Get upcoming events from Google Calendar')
async def upcoming_events_command(ctx):
    events = get_upcoming_events()
    if not events:
       await ctx.send('No upcoming events found.')
    else:
       event_list = '\n\n'.join([create_discord_event(event) for event in events])
       await ctx.send(f'Upcoming events:\n\n{event_list}')


# Discord bot event for when the bot is ready
@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')


# Voice channel inactivity timeout (in seconds)
INACTIVITY_TIMEOUT = 600

# Voice channel inactivity check interval (in seconds)
INACTIVITY_CHECK_INTERVAL = 60

# Dictionary to store the last activity time for each voice channel
last_activity = {}


# Function to check for inactivity in voice channels
async def check_inactivity():
    while True:
        for voice_channel in bot.voice_clients:
            if voice_channel.is_playing() or voice_channel.is_paused():
                last_activity[voice_channel.channel.id] = discord.utils.utcnow()
            elif voice_channel.channel.id in last_activity and (discord.utils.utcnow() - last_activity[
                voice_channel.channel.id]).total_seconds() >= INACTIVITY_TIMEOUT:
                await voice_channel.disconnect()
                del last_activity[voice_channel.channel.id]
        await asyncio.sleep(INACTIVITY_CHECK_INTERVAL)


# Start the Discord bot
bot.run(DISCORD_TOKEN)
