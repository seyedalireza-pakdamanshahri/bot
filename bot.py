import discord
import networkx as nx
import matplotlib.pyplot as plt
from discord.ext import commands
from collections import defaultdict
import logging
import os
import sqlite3
from flask import Flask
from threading import Thread

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

conn = sqlite3.connect('bot.db')

conn.execute('''CREATE TABLE IF NOT EXISTS invites
                (guild_id TEXT,
                invite_code TEXT,
                uses INTEGER,
                inviter TEXT,
                member TEXT);''')

G = nx.DiGraph()

app = Flask('')

@app.route('/')
def home():
    return "Hello. I am alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

@bot.event
async def on_ready():
    logging.info(f'We have logged in as {bot.user}')
    for guild in bot.guilds:
        await guild.chunk()

@bot.event
async def on_invite_create(invite):
    conn.execute("INSERT INTO invites (guild_id, invite_code, uses) VALUES (?, ?, ?)",
                 (str(invite.guild.id), invite.code, invite.uses))
    conn.commit()

@bot.event
async def on_guild_join(guild):
    invites = await guild.invites()
    for invite in invites:
        conn.execute("INSERT INTO invites (guild_id, invite_code, uses) VALUES (?, ?, ?)",
                     (str(guild.id), invite.code, invite.uses))
    conn.commit()

@bot.event
async def on_invite_create(invite):
    conn.execute("INSERT INTO invites (guild_id, invite_code, uses, inviter) VALUES (?, ?, ?, ?)",
                 (str(invite.guild.id), invite.code, invite.uses, str(invite.inviter)))
    conn.commit()
    logging.info(f"Invite created: Guild ID {invite.guild.id}, Code {invite.code}, Uses {invite.uses}, Inviter {invite.inviter}")
@bot.event
async def on_member_join(member):
    try:
        new_invites = await member.guild.invites()
        for invite in new_invites:
            cursor = conn.execute("SELECT * FROM invites WHERE guild_id = ? AND invite_code = ?",
                                  (str(member.guild.id), invite.code))
            old_invite = cursor.fetchone()
            if old_invite and old_invite[2] < invite.uses:
                conn.execute("UPDATE invites SET uses = ?, member = ?, inviter = ? WHERE guild_id = ? AND invite_code = ?",
                             (invite.uses, str(member), str(invite.inviter), str(member.guild.id), invite.code))
                conn.commit()
                break
    except Exception as e:
        logging.error(f"Error in on_member_join: {e}")



# Similar logging for other events...

@bot.command()
async def draw_tree(ctx):
    cursor = conn.execute("SELECT * FROM invites WHERE member IS NOT NULL")
    count = 0
    for row in cursor:
        if row[3] is not None and row[4] is not None:
            G.add_edge(row[3], row[4])
            count += 1

    logging.info(f"Added {count} edges to the graph.")

    if count == 0:
        await ctx.send("No edges to draw.")
        return

    plt.figure(figsize=(10,10))
    pos = nx.spring_layout(G)  
    nx.draw(G, pos, with_labels=True, font_weight='bold', node_color='skyblue', node_size=1500, edge_color='gray')
    
    plt.savefig('tree.png')
    try:
        await ctx.send(file=discord.File('tree.png'))
    except Exception as e:
        logging.error(f"Error in draw_tree: {e}")
    finally:
        os.remove('tree.png')

# Start the web server
keep_alive()

# Process commands and respond to messages
@bot.event
async def on_message(message):
    if not message.author.bot:
        await bot.process_commands(message)
        if message.content.lower() == "hello":
            await message.channel.send("Hi!")

# Run the bot
bot.run(os.getenv('DISCORD_BOT_TOKEN'))

