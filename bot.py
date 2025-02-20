import discord
from discord.ext import commands, tasks
import sqlite3
import random
from datetime import datetime, timedelta
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Database setup
conn = sqlite3.connect('blackjack.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users
             (user_id INTEGER PRIMARY KEY, 
              balance INTEGER DEFAULT 10000,
              last_daily TEXT,
              current_table INTEGER,
              absences INTEGER DEFAULT 0)''')
conn.commit()

class Player:
    def __init__(self, user):
        self.user = user
        self.bet = 0
        self.hand = []
        self.stand = False
        self.busted = False
        self.blackjack = False

class Table:
    def __init__(self, channel):
        self.channel = channel
        self.players = []
        self.shoe = []
        self.cut = 0
        self.dealer_hand = []
        self.game_phase = "waiting"
        self.betting_timeout = 60
        self.round_counter = 0
        self.timer_task = None  # Track the active betting timer
        self.reshuffle()

    def reshuffle(self):
        self.shoe = []
        for _ in range(7):
            deck = [str(n) for n in range(2, 11)] * 4 + ['J', 'Q', 'K', 'A'] * 4
            self.shoe += deck
        random.shuffle(self.shoe)
        self.cut = random.randint(50, 200)
    
    def add_player(self, player):
        if len(self.players) < 5:
            self.players.append(player)
            return True
        return False

tables = {}

def get_user(user_id):
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    return c.fetchone()

def update_user(user_id, **kwargs):
    setters = []
    values = []
    for key, value in kwargs.items():
        setters.append(f"{key} = ?")
        values.append(value)
    values.append(user_id)
    query = f"UPDATE users SET {', '.join(setters)} WHERE user_id = ?"
    c.execute(query, values)
    conn.commit()

def calculate_hand(hand):
    value = 0
    aces = 0
    for card in hand:
        if card in ['J', 'Q', 'K']:
            value += 10
        elif card == 'A':
            value += 11
            aces += 1
        else:
            value += int(card)
    soft = False
    while value > 21 and aces:
        value -= 10
        aces -= 1
    if aces > 0:
        soft = True
    return value, soft

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.command()
async def join(ctx):
    user_id = ctx.author.id
    channel = ctx.channel

    user_record = get_user(user_id)
    if user_record is not None and user_record[3]:
        await ctx.send("You're already in a table. Use !leave first.")
        return

    if channel.id not in tables:
        tables[channel.id] = Table(channel)
    
    table = tables[channel.id]

    if any(p.user.id == user_id for p in table.players):
        await ctx.send("You're already at this table!")
        return
    
    if len(table.players) >= 5:
        await ctx.send("Table is full (5/5 players)")
        return
    
    if not get_user(user_id):
        c.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
        conn.commit()
    
    table.players.append(Player(ctx.author))
    update_user(user_id, current_table=channel.id)
    await ctx.send(f"{ctx.author.mention} joined the table!")

    # If this is the first player and no betting timer is running, start the betting phase.
    if len(table.players) == 1 and table.timer_task is None:
        table.game_phase = "betting"
        await table.channel.send("New round starting! Place bets with !bet (25-1000 chips)")
        table.timer_task = bot.loop.create_task(betting_timer(table))

@bot.command()
async def leave(ctx):
    user_id = ctx.author.id
    channel = ctx.channel
    
    if channel.id not in tables:
        await ctx.send("No table in this channel")
        return
    
    table = tables[channel.id]
    player = next((p for p in table.players if p.user.id == user_id), None)
    
    if not player:
        await ctx.send("You're not in this table")
        return
    
    table.players.remove(player)
    update_user(user_id, current_table=None)
    await ctx.send(f"{ctx.author.mention} left the table")
    
    if not table.players:
        del tables[channel.id]

@bot.command()
async def bet(ctx, amount: int):
    user_id = ctx.author.id
    channel = ctx.channel
    
    if channel.id not in tables:
        await ctx.send("No table in this channel")
        return
    
    table = tables[channel.id]
    player = next((p for p in table.players if p.user.id == user_id), None)
    
    if not player:
        await ctx.send("You're not in this table")
        return
    
    if table.game_phase != "betting":
        await ctx.send("Betting not active")
        return
    
    user_data = get_user(user_id)
    if amount < 25 or amount > 1000:
        await ctx.send("Bet must be between 25-1000 chips")
        return
    if amount > user_data[1]:
        await ctx.send("Insufficient chips")
        return
    
    player.bet = amount
    update_user(user_id, balance=user_data[1] - amount)
    await ctx.send(f"{ctx.author.mention} bet {amount} chips")
    
    if all(p.bet for p in table.players):
        # Cancel any existing betting timer to prevent overlaps.
        if table.timer_task is not None:
            table.timer_task.cancel()
            table.timer_task = None
        await start_game(table)

async def start_game(table):
    table.game_phase = "playing"
    
    # Deal initial cards
    for _ in range(2):
        for player in table.players:
            player.hand.append(table.shoe.pop())
        table.dealer_hand.append(table.shoe.pop())
    
    # Check for dealer blackjack
    dealer_value, _ = calculate_hand(table.dealer_hand)
    
    await table.channel.send(f"Dealer: {table.dealer_hand[0]} [HIDDEN]")
    for player in table.players:
        value, _ = calculate_hand(player.hand)
        if value == 21:
            await table.channel.send(f"{player.user.mention}: {' '.join(player.hand)} ({value}) BLACKJACK!")
        else:
            await table.channel.send(f"{player.user.mention}: {' '.join(player.hand)} ({value})")

    if dealer_value == 21:
        await table.channel.send(f"Dealer: {table.dealer_hand[0]} {table.dealer_hand[1]}")
        await table.channel.send(f"Dealer has BLACKJACK")
        await end_game(table)
        return
    
    # Player turns
    for player in table.players:
        await player_turn(table, player)
    
    # Dealer turn
    await dealer_turn(table)
    
    await end_game(table)

async def player_turn(table, player):
    user_data = get_user(player.user.id)
    balance = user_data[1]
    amount = player.bet
    value, _ = calculate_hand(player.hand)
    if value == 21:
        return
    await table.channel.send(f"{player.user.mention}'s turn. Hand: {' '.join(player.hand)} | Total: {value}")
    
    while True:
        try:
            msg = await bot.wait_for(
                'message', 
                check=lambda m: m.author == player.user and m.channel == table.channel,
                timeout=30
            )
            
            if msg.content.lower() == '!hit':
                player.hand.append(table.shoe.pop())
                value, _ = calculate_hand(player.hand)
                await table.channel.send(f"New card: {player.hand[-1]} | Total: {value}")
                
                if value > 21:
                    player.busted = True
                    await table.channel.send("Bust!")
                    break
                if value == 21:
                    break

            if msg.content.lower() == '!double':
                if balance >= amount:
                    player.hand.append(table.shoe.pop())
                    player.bet += amount
                    balance -= amount
                    update_user(player.user.id, balance=balance)
                    await table.channel.send(f"{player.user.mention} doubled! | New balance: {balance}")
                    value, _ = calculate_hand(player.hand)
                    await table.channel.send(f"New card: {player.hand[-1]} | Total: {value}")

                    if value > 21:
                        player.busted = True
                        await table.channel.send("Bust!")

                    break
                else:
                    await table.channel.send("Insufficient funds!")
            
            elif msg.content.lower() == '!stand':
                break
        
        except asyncio.TimeoutError:
            await table.channel.send("Timed out. Standing automatically.")
            break

async def dealer_turn(table):
    await table.channel.send(f"Dealer's hand: {table.dealer_hand[0]} {table.dealer_hand[1]}")
    
    while True:
        value = calculate_hand(table.dealer_hand)[0]
        if value >= 21:
            break
        if value < 17:
            table.dealer_hand.append(table.shoe.pop())
            await table.channel.send(f"Dealer hits: {table.dealer_hand[-1]}")
        else:
            break
    
    await table.channel.send(f"Dealer's final hand: {' '.join(table.dealer_hand)} ({value})")

async def end_game(table):
    dealer_value, _ = calculate_hand(table.dealer_hand)
    dealer_bust = dealer_value > 21
    dealer_blackjack = dealer_value == 21 and len(table.dealer_hand) == 2
    
    for player in table.players:
        user_data = get_user(player.user.id)
        balance = user_data[1]
        value, _ = calculate_hand(player.hand)
        
        if player.busted:
            result = "lost (bust)"
        elif value == 21 and len(player.hand) == 2 and not dealer_blackjack:
            winnings = int(player.bet * 2.5)
            balance += winnings
            result = f"won {winnings} (Blackjack!)"
        elif dealer_bust or value > dealer_value:
            winnings = player.bet * 2
            balance += winnings
            result = f"won {winnings}"
        elif value == dealer_value:
            balance += player.bet
            result = "pushed"
        else:
            result = "lost"
        
        update_user(player.user.id, balance=balance)
        await table.channel.send(f"{player.user.mention} {result} | New balance: {balance}")
        
        # Reset player for next round
        player.bet = 0
        player.hand = []
        player.busted = False

    # Reset table for new round
    table.dealer_hand = []
    table.round_counter += 1

    if len(table.shoe) < table.cut:
        table.reshuffle()
        await table.channel.send("Shoe reshuffled!")
    
    await table.channel.send("New round starting! Place bets with !bet (25-1000 chips)")
    # Cancel any existing betting timer and start a new one
    if table.timer_task is not None:
        table.timer_task.cancel()
        table.timer_task = None
    table.game_phase = "betting"
    table.timer_task = bot.loop.create_task(betting_timer(table))

async def betting_timer(table):
    await asyncio.sleep(60)
    
    # Iterate over a copy of the players list to safely remove inactive players
    for player in table.players[:]:
        if player.bet == 0:
            user_data = get_user(player.user.id)
            current_absences = user_data[4] + 1
            update_user(player.user.id, absences=current_absences)
            if current_absences >= 5:
                await table.channel.send(f"{player.user.mention} removed for inactivity")
                table.players.remove(player)
                update_user(player.user.id, current_table=None)
    
    # Clear the timer task now that this timer is done
    table.timer_task = None
    
    if table.players:
        await start_game(table)

@bot.command()
async def daily(ctx):
    user_id = ctx.author.id
    user_data = get_user(user_id)
    
    if not user_data:
        await ctx.send("Join a table first!")
        return
    
    last_daily = datetime.fromisoformat(user_data[2]) if user_data[2] else None
    
    if last_daily and (datetime.utcnow() - last_daily) < timedelta(hours=24):
        await ctx.send("Come back later for your daily chips!")
        return
    
    new_balance = user_data[1] + 1000
    update_user(user_id, balance=new_balance, last_daily=datetime.utcnow().isoformat())
    await ctx.send(f"💸 1,000 chips added! New balance: {new_balance}")

@bot.command()
async def balance(ctx):
    user_id = ctx.author.id
    user_data = get_user(user_id)
    
    if user_data:
        await ctx.send(f"Current balance: {user_data[1]} chips")
    else:
        await ctx.send("Join a table first!")

# IMPORTANT: Replace the token below with an environment variable or secure token.
bot.run(DISCORD_BOT_TOKEN)
