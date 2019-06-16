import asyncio
import json
import random
import re
import time
import io
from datetime import timedelta
from typing import Tuple

import discord
from num2words import num2words

from redisdb import REDISDB
from osu_utils.utils import osu_getuserinfo, osu_drawuserinfo


async def poll(client: discord.Client,
               message: discord.Message) -> Tuple[str, str]:
    # Regex stuff
    re_match = re.match(r'^\$poll (\d{1,4}) (.+)', message.content)
    seconds = int(re_match.group(1))
    prompt = re_match.group(2)
    channel = message.channel

    try:
        # delete previous command
        await client.delete_message(message)
    except discord.errors.Forbidden:
        # missing permissions
        pass

    def td(s: float) -> str: return str(timedelta(seconds=int(s)))

    embed = discord.Embed(title='Poll', description=prompt +
                          '\nUse :thumbsup: or :thumbsdown: to vote!' +
                          f'\nPoll finalizes in {td(seconds)}')
    poll_msg = await client.send_message(
        channel, embed=embed
    )
    # Show how much seconds the poll has got
    rem_seconds = seconds
    poll_seconds_refresh = 5
    while rem_seconds >= poll_seconds_refresh:
        await asyncio.sleep(poll_seconds_refresh)
        rem_seconds -= poll_seconds_refresh
        embed = discord.Embed(title='Poll', description=prompt +
                              '\nUse :thumbsup: or :thumbsdown: to vote!' +
                              f'\nPoll finalizes in {td(rem_seconds)}')
        ctime = time.time()
        poll_msg = await client.edit_message(poll_msg, embed=embed)
        deltatime = time.time() - ctime
        rem_seconds -= deltatime
    await asyncio.sleep(rem_seconds)
    # Poll finalized
    poll_msg = await client.get_message(channel, poll_msg.id)
    yes = 0
    no = 0
    for r in poll_msg.reactions:
        r: discord.Reaction
        print(r.emoji)
        if r.emoji == '👍':
            yes = r.count
        if r.emoji == '👎':
            no = r.count
    embed = discord.Embed(title='Poll', description=prompt +
                          '\nUse :thumbsup: or :thumbsdown: to vote!' +
                          f'\nPoll has been finished, results are final.' +
                          f'\n\nYes: {yes}\nNo: {no}')
    await client.edit_message(poll_msg, embed=embed)
    return str(yes), str(no)


async def num_convert_word(client: discord.Client,
                           message: discord.Message):
    re_match = re.match(r'^\$word (\d{1,308})( [a-zA-Z_]{0,5})?',
                        message.content)
    num = re_match.group(1)
    locale = re_match.group(2)
    if int(num) >= int('1' + '0' * 306):  # floating point precision
        word = 'Number must be less than 1' + '0' * 306
    else:
        if locale is not None:
            try:
                word = num2words(int(num), lang=locale.strip())
            except NotImplementedError:
                word = 'Unsupported language'
        else:
            word = num2words(int(num))
    # Special cases
    spec_cases = {
        '69': 'NSFW!',
        '420': 'Trees',
        '666': 'o_O',
        '1337': 'WOW UR COOL',
    }
    if num in spec_cases:
        word += ' ' + spec_cases[num]
    try:
        await client.send_message(message.channel, word)
    except discord.errors.HTTPException:
        await client.send_message(message.channel, 'Resulting text was too '
                                  'long to send!')


async def reminder(client: discord.Client,
                   message: discord.Message):
    re_match = re.match(r'^\$reminder (\d+) (.+)', message.content)
    seconds = re_match.group(1)
    reminder_text = re_match.group(2)
    await client.send_message(message.channel, f'Reminder `{reminder_text}`'
                              ' has been set.')
    await asyncio.sleep(int(seconds))
    await client.send_message(message.channel, f'{message.author.mention}'
                              f' {reminder_text}')


async def autoyeet_toggle(client: discord.Client,
                          message: discord.Message):
    yeetdb = json.loads(REDISDB.get('AUTOYEET').decode())
    if message.channel.id not in yeetdb:
        yeetdb[message.channel.id] = False
    yeetdb[message.channel.id] = not yeetdb[message.channel.id]
    REDISDB.set('AUTOYEET', json.dumps(yeetdb))
    if yeetdb[message.channel.id]:
        # yeeting on
        await client.send_message(message.channel, 'Autoyeet on')
        # start the yeet loop
        await autoyeet_loop(client, message)
    else:
        # yeeting off
        await client.send_message(message.channel, 'Autoyeet off')


async def autoyeet_loop(client: discord.Client,
                        message: discord.Message):
    yeetdb = json.loads(REDISDB.get('AUTOYEET').decode())
    yeetdb[message.channel.id] = True
    REDISDB.set('AUTOYEET', json.dumps(yeetdb))
    while True:
        await asyncio.sleep(random.randint(5, 120))
        yeetdb = json.loads(REDISDB.get('AUTOYEET').decode())
        if not yeetdb[message.channel.id]:
            break
        await client.send_message(message.channel, 'YEET!')


async def autoyeet_loop_channelid(client: discord.Client,
                                  channelid: str):
    channel = client.get_channel(channelid)
    yeetdb = json.loads(REDISDB.get('AUTOYEET').decode())
    yeetdb[channel.id] = True
    REDISDB.set('AUTOYEET', json.dumps(yeetdb))
    while True:
        await asyncio.sleep(random.randint(5, 120))
        yeetdb = json.loads(REDISDB.get('AUTOYEET').decode())
        if not yeetdb[channel.id]:
            break
        await client.send_message(channel, 'YEET!')


async def love_calculator(client: discord.Client,
                          message: discord.Message):
    # message preprocessing
    re_match = re.match(r'^\$lovecalc (.+)', message.content)
    re_persons = re_match.group(1).strip().split(',')
    if len(re_persons) != 2:
        await client.send_message(message.channel, f'Incorrect usage')
        return
    persons = ','.join(p.strip().lower() for p in re_persons)
    # reversed
    r_persons = ','.join(p.strip().lower() for p in re_persons[::-1])
    lovedb = json.loads(REDISDB.get('LOVEDB').decode())
    if persons not in lovedb and r_persons not in lovedb:
        love = random.randint(0, 100)
        lovedb[persons] = love
        REDISDB.set('LOVEDB', json.dumps(lovedb))
    # format response
    score, r_score = lovedb.get(persons), lovedb.get(r_persons)
    love = score if score is not None else r_score
    await client.send_message(message.channel, f'I\'d give '
                              f'{persons.split(",")[0]} and '
                              f'{persons.split(",")[1]} a love score of '
                              f'{love}%')


async def osu_userinfo(client: discord.Client,
                       message: discord.Message):
    """
    Get user info for an osu player through osu API
    """
    re_match = re.match(r'^\$osu user (.+)', message.content)
    user_name = re_match.group(1)
    info = await osu_getuserinfo(user_name)
    if not info:
        await client.send_message(message.channel, 'User not found!')
        return
    image = osu_drawuserinfo(info[0])
    image_bytes = io.BytesIO()
    image.save(image_bytes, format='png')
    await client.send_file(message.channel, io.BytesIO(image_bytes.getvalue()),
                           filename='stats.png')


# honestly i have no idea what i was going for below here.

async def make_macro(client: discord.Client,
                     message: discord.Message):
    """
    Allows a user to create a macro by name
    # Macro commands
        say xxx
    """
    pass


async def run_macro(client: discord.Client,
                    message: discord.Message):
    """
    Allows the user to run the macro by name
    """
    pass


async def delete_macro(client: discord.Client,
                       message: discord.Message):
    """
    Deletes the macro by name
    """
    pass


async def profanity_filter(client: discord.Client,
                           message: discord.Message):
    profanity = [
        'fuck', 'cunt', 'shit',
    ]
    if any(x in message.content.lower() for x in profanity):
        await client.send_message(message.channel, 'Did you just swear on'
                                  ' my christian minecraft server?!11!!')
