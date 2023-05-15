import discord
import networkx as nx
import matplotlib.pyplot as plt
from discord.ext import commands
import logging
import os
import sqlite3
from flask import Flask
from threading import Thread

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

conn = sqlite3.connect('bot.db')

# Check if 'invites' table exists
cursor = conn.cursor()
cursor.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='invites';")
table_exists = cursor.fetchone()

if not table_exists:
    # If 'invites' doesn't exist, create it
    conn.execute('''
        CREATE TABLE IF NOT EXISTS invites
        (guild_id TEXT,
        invite_code TEXT,
        uses INTEGER,
        inviter TEXT,
        member TEXT,
        description TEXT,
        PRIMARY KEY (guild_id, member));
    ''')
else:
    # If 'invites' exists, create 'new_invites', copy data, drop 'invites' and rename 'new_invites'
    conn.execute('''
        CREATE TABLE IF NOT EXISTS new_invites
        (guild_id TEXT,
        invite_code TEXT,
        uses INTEGER,
        inviter TEXT,
        member TEXT,
        description TEXT,
        PRIMARY KEY (guild_id, member));
    ''')

    conn.execute('''
        INSERT INTO new_invites
        SELECT * FROM invites
        WHERE guild_id IS NOT NULL AND member IS NOT NULL;
    ''')

    conn.execute('DROP TABLE IF EXISTS invites;')

    conn.execute('ALTER TABLE new_invites RENAME TO invites;')

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


@bot.command()
async def add_inviter(ctx, member: discord.Member, inviter: discord.Member):
    if ctx.author.guild_permissions.administrator:  # Ensure the command is run by an admin
        # Insert a new row or update an existing one in the invites table
        conn.execute(
            "INSERT INTO invites (guild_id, member, inviter, description) VALUES (?, ?, ?, ?) ON CONFLICT(guild_id, member) DO UPDATE SET inviter = ?, description = ?",
            (str(ctx.guild.id), str(member), str(inviter), "", str(inviter),
             ""))
        conn.commit()
        await ctx.send(
            f"Updated the inviter of {member.name} to {inviter.name}.")
    else:
        await ctx.send("You do not have permission to use this command.")


@bot.command()
async def draw_tree(ctx):
    cursor = conn.execute("SELECT * FROM invites WHERE member IS NOT NULL")
    count = 0
    G = nx.DiGraph()  # create a new graph each time you draw
    for row in cursor:
        if row[3] is not None and row[4] is not None:
            G.add_edge(row[3], row[4])
            count += 1

    logging.info(f"Added {count} edges to the graph.")

    if count == 0:
        await ctx.send("No edges to draw.")
        return

    plt.figure(figsize=(10, 10))
    pos = nx.spring_layout(G)
    nx.draw(G,
            pos,
            with_labels=True,
            font_weight='bold',
            node_color='skyblue',
            node_size=1500,
            edge_color='gray')

    plt.savefig('tree.png')
    try:
        await ctx.send(file=discord.File('tree.png'))
    except Exception as e:
        logging.error(f"Error in draw_tree: {e}")
    finally:
        os.remove('tree.png')


@bot.command()
async def edit(ctx, member: discord.Member, new_description: str):
    if ctx.author.guild_permissions.administrator:  # Ensure the command is run by an admin
        conn.execute(
            "UPDATE invites SET description = ? WHERE guild_id = ? AND member = ?",
            (new_description, str(ctx.guild.id), str(member.id)))

        conn.commit()
        await ctx.send(
            f"Updated the description of {member.name} to {new_description}.")
    else:
        await ctx.send("You do not have permission to use this command.")


@bot.command()
async def get_description(ctx, member: discord.Member):
    cursor = conn.execute(
        "SELECT description FROM invites WHERE guild_id = ? AND member = ?",
        (str(ctx.guild.id), str(member.id)))
    row = cursor.fetchone()
    if row is not None and row[0] is not None:
        await ctx.send(f"The description of {member.name} is {row[0]}.")
    else:
        await ctx.send(f"No description found for {member.name}.")


keep_alive()


@bot.event
async def on_message(message):
    if not message.author.bot:
        await bot.process_commands(message)
        if message.content.lower() == "hello":
            await message.channel.send("Hi!")


bot.run(os.getenv('DISCORD_BOT_TOKEN'))
