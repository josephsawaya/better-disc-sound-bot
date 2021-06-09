from typing import Dict
import discord
import os
from pathlib import PurePath
import queue
import asyncio
from dotenv import load_dotenv

load_dotenv()


class Sound():
    path: str
    chan: discord.VoiceChannel
    name: str

    def __repr__(self) -> str:
        return self.name


sound_queue = queue.Queue(20)
queue_event = asyncio.Event()


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # create the background task and run it in the background
        self.bg_task = self.loop.create_task(self.my_background_task())

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

    async def my_background_task(self):
        await self.wait_until_ready()
        while True:
            await queue_event.wait()
            queue_event.clear()
            print("received sound")
            sound: Sound = sound_queue.get()
            connection = await sound.chan.connect()
            finish_event = asyncio.Event()

            def after(error):
                finish_event.set()
            connection.play(discord.FFmpegPCMAudio(sound.path), after=after)

            await finish_event.wait()
            await connection.disconnect()
            print("disconnecting")
            if not sound_queue.empty():
                queue_event.set()


client = MyClient()


discord.opus.load_opus("/usr/lib64/libopus.so.0")


@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.lower().startswith('$upload'):
        if '/' not in message.content:
            filename = message.content.split()[1]
            guild_id = message.guild.id
            if len(message.attachments) == 1:
                sound_file = message.attachments[0]
                if sound_file.content_type == 'audio/mpeg':
                    if not os.path.exists(str(guild_id)):
                        os.makedirs(str(guild_id))
                    else:
                        await message.channel.send('Congrats on uploading your first sound!')
                    await sound_file.save(PurePath(str(guild_id), filename + ".mp3"))
                    await message.channel.send('Sound: ' + filename + ' created!')
                else:
                    await message.channel.send('Why are you trying to upload something other than a sound?')
            else:
                await message.channel.send('Wrong number of attachments only try uploading one sound at a time')
        else:
            await message.channel.send('I do the bare minimum when validating input')

    if message.content.lower().startswith('$play'):
        target_channel = message.content.split()[2]
        found = False
        for chan in message.guild.voice_channels:
            if chan.name == target_channel:
                found = True
                guild_id = message.guild.id
                target_sound = message.content.split()[1]
                path = str(guild_id) + "/" + target_sound + ".mp3"
                file_exists = os.path.exists(path)
                if(file_exists):
                    sound = Sound()
                    sound.chan = chan
                    sound.path = path
                    sound.name = target_sound
                    sound_queue.put(sound)
                    queue_event.set()
                else:
                    await message.channel.send('Sound doesn\'t exist..')
        if not found:
            await message.channel.send('Channel doesn\'t exist..')

    if message.content.lower().startswith('$queue'):
        await message.channel.send(list(sound_queue.queue))

    if message.content.lower().startswith('$clear'):
        with sound_queue.mutex:
            sound_queue.queue.clear()
        await message.channel.send('Queue cleared')


client.run(os.environ["TOKEN"])
