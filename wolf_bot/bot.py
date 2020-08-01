import yaml
import os

import pathlib

from random import shuffle, choice

from dotenv import load_dotenv

import discord
from discord.ext import commands
from discord.ext.commands import Bot

bot = commands.Bot(command_prefix='!')
client = discord.Client()

PRESTART = 'prestart' 
START = 'start'
DAY_TO_NIGHT = 'day_to_night'
VOTING_WOLF = 'voting_wolf'
VOTING_WITCH_HEAL = 'voting_witch_heal'
VOTING_WITCH_KILL = 'voting_witch_kill'
NIGHT_TO_DAY = 'night_to_day'
VOTING_VILLAGE = 'voting_village'
KILLING = 'killing'
STATES = [
	PRESTART, START, DAY_TO_NIGHT, VOTING_WOLF, VOTING_WITCH_HEAL, 
	VOTING_WITCH_KILL, KILLING, NIGHT_TO_DAY, VOTING_VILLAGE
]

VILLAGER = 'villager'
WITCH = 'witch'
WOLF = 'wolf'
HUNTER = 'hunter'

lang = 'de'

translations = {}

with open(pathlib.Path().absolute() / 'data' / 'translations.yml') as yaml_file:
	translations = yaml.full_load(yaml_file)

def translate(txt):
	global translations, lang
	if txt in translations[lang]:
		tra = translations[lang][txt]
		if isinstance(tra, list):
			return choice(tra)
		else:
			return tra
	else:
		return f'TRANSLATE_{text}'


### discord helper functions
def get_member_from_channel(channel):
	"""Get all user from the channel"""
	mem = [m for m in channel.members if not m.bot and m.voice]
	print(translate('mem_in_chan').format(len(mem), channel.name))
	return mem


def get_voice_channel(channel_name):
	"""Get voice channel by name."""
	for guild in bot.guilds:
		for channel in guild.voice_channels:
			if channel.name == channel_name:
				return guild, channel
	print(f'Error: could not find voice channel named {channel_name}')
	return None, None


def get_text_channel(guilds, channel_name):
	"""Get text channel by name."""
	for guild in guilds:
		for channel in guild.text_channels:
			if channel.name == channel_name:
				return guild, channel
	print(f'Error: could not find text channel named {channel_name}')
	return None, None

def get_channel(guilds, channel_name):
	"""Get voice or text channel by name."""
	for guild in guilds:
		for channel in guild.voice_channels:
			if channel.name == channel_name:
				return guild, channel
		for channel in guild.text_channels:
			if channel.name == channel_name:
				return guild, channel
	print(f'Error: could not find channel named {channel_name}')
	return None, None


class WerewolfGame:
	def __init__(self, bot, settings: dict = None,
			text_channel_name: str = 'werwolf',
			day_channel_name: str = 'Tag',
			werewolf_channel_name: str = 'Werwölfe'):
		if not settings:
			self.settings = {
				WITCH: 1,
				WOLF: 1,
				#HUNTER: 1,
			}
		else:
			self.settings = settings
		
		# just set channel names
		self.text_channel_name = text_channel_name
		self.day_channel_name = day_channel_name
		self.werewolf_channel_name = werewolf_channel_name
		
		# Discord bot
		self.bot = bot
		
		self.cleanup()


	async def get_create_all_channel(self):
		# Main text channel for commands
		self.text_channel = await self.get_create_text_channel(
			self.text_channel_name)

		# voice channel for day
		self.day_channel = await self.get_create_voice_channel(
			self.day_channel_name)

		# voice channel for werewolfs at night
		self.werewolf_channel = await self.get_create_voice_channel(
			self.werewolf_channel_name)

	async def get_create_text_channel(self, channel_name):
		_, channel = get_text_channel(channel_name)
		if not channel:
			return await bot.guilds[0].create_text_channel(channel_name)
		return channel

	async def get_create_voice_channel(self, channel_name):
		_, channel = get_voice_channel(channel_name)
		if not channel:
			return await bot.guilds[0].create_voice_channel(channel_name)
		return channel

	async def start(self):
		"""Start a new game!"""
		self.cleanup()
		self.current_state = START
		print(translate('new_game'))
		# 1. get all member from day-channel
		day_player = get_member_from_channel(self.day_channel)
		# 2. shuffle player
		shuffle(day_player)
		# 3. player to their roles
		await self.assign_roles(day_player)
		await self.text_channel.send(translate('new_game'))
		# 4. start the first game loop - switch from day to night
		await self.day_to_night()

	def cleanup(self):
		"""Set values from last round to empty."""
		# list of all player 
		self.player = {}

		# temprary kill list
		self.kill_list = []

		# current game state
		self.current_state = PRESTART

		# player the wolfes voted to kill
		self.wolf_votes = {}

		# list of wolfes who already voted
		self.wolf_voted = []

		# True, if the witch has used her ealing potion
		self.witch_healed = False

		# True, if the witch has used her poison
		self.witch_killed = False


	async def assign_roles(self, player: list):
		"""Assign all roles to player."""
		assert isinstance(player, list)
		self.player = {}
		index = 0
		# assign special roles
		for role, amount in self.settings.items():
			await self.assign_role(player[index:index+amount], role)
			index += amount
		# the rest will become villagers
		await self.assign_role(player[index:], VILLAGER)

	async def assign_role(self, player: list, role: str):
		"""Assign list of player to a specific role."""
		assert isinstance(player, list)
		assert isinstance(role, str)
		self.player[role] = player
		for current_player in player:
			await current_player.send(
				translate('you_are') +
				translate(role))

	# -- MAIN GAME LOOP --
	async def day_to_night(self):
		"""Switch from day to night, move everyone in his/her own little voice chat."""
		self.current_state = DAY_TO_NIGHT
		move_player = []
		non_wolf = 0
		for key, value in self.player.items():
			# create list of channel and player to move
			if key == WOLF:
				for member in value:
					move_player.append((self.werewolf_channel, member))
			else:
				for member in value:
					non_wolf += 1
					# create channel if needed
					channel = self.get_create_voice_channel(str(non_wolf))
					# hide werewolf-channel from user
					await self.werewolf_channel.set_permissions(
						member, view_channel=False)
					move_player.append((channel, member))
		
		# suffle so werewolfs do get moved randomly and not first/last
		shuffle(move_player)

		# and now the moving itself
		for channel, member in move_player:
			await member.move_to(channel)

		# the night has begone, the wolfs should start voting for the kill now!
		await self.voting_wolfs_start()

	async def voting_wolfs_start(self):
		"""Send text to each werewolf that he/she has to vote for a kill."""
		self.current_state = VOTING_WOLF
		self.wolf_votes = {}
		self.wolf_voted = []
		for wolf in self.player[WOLF]:
			await wolf.send(translate('who_to_kill'))
		# end of this part of the round, we now need to wait for incoming 
		# messages from wolfs

	async def wolf_send_vote(self, msg):
		if msg.author in self.wolf_voted:
			# only one vote per wolf, you can not change your vote!
			await msg.author.send(translate('already_voted'))
			return
		member = self.find_player(msg.content)
		if not member:
			await msg.author.send(translate('does_not_exist').format(msg.content))
			return
		elif self.is_wolf(member):
			await msg.author.send(translate('is_a_wolf'))
			return
		self.wolf_votes.setdefault(member, 0)
		self.wolf_votes[member] += 1
		self.wolf_voted.append(msg.author)
		# now we need to check if all wolfes have voted
		return await self.wolfes_check_voting_end()
		
	async def wolfes_check_voting_end(self):
		"""evaluate the voting if all wolves decided on a victim."""
		if sum(self.player[WOLF]) == sum(self.wolf_voted):
			# get player with most votes
			member = max(self.wolf_votes, key=wolf_votes.get)
			print('marked to kill: ', player)
			# save in kill-list
			self.kill_list.append(player)
			await self.voting_witch_heal()
		# else: voting not over, wait for other player to vote

	async def voting_witch_heal(self):
		self.current_state = VOTING_WITCH_HEAL
		# We tell the witch who will get killed and ask to heal
		if not self.witch_healed:
			kill_name = f'{self.kill_list[0].name} ({self.kill_list[0].nick})'
			await self.player[WITCH].send(translate('ask_heal').format(kill_name))
		else:
			await self.voting_witch_kill()

	async def witch_awnsered_heal(self, msg):
		if msg.content.lower() in ['yes', 'ja']:
			await self.player[WITCH].send(translate('witch_spare'))
			self.kill_list = []
			self.witch_healed = True
			await self.voting_witch_kill()
		elif msg.content.lower() in ['no', 'nein']:
			await self.player[WITCH].send(translate('witch_ignore'))
			await self.voting_witch_kill()
		else:
			await self.player[WITCH].send(translate('witch_repeat_heal'))
			return
		# the witch decided, go to next step: ask her to kill someone
	
	async def voting_witch_kill(self):
		self.current_state = VOTING_WITCH_KILL
		# Ask the witch if she wants to poison someone
		if not self.witch_killed:
			await self.player[WITCH].send(translate('ask_kill'))
		else:
			await self.kill_player()

	async def witch_answered_kill(self, msg):
		# Ask the witch if she wants to poison someone
		# WE ASSUME A PLAYER CAN NOT BE NAMED "no", otherwise he will always get killed
		# this way a player can not cheat/get invincible by calling himself "no"
		member = self.find_player(msg.content)
		if member:
			await self.player[WITCH].send(translate('witch_kill').format(member))
			self.kill_list.append(member)
			self.witch_killed = True
			await self.kill_player()
		elif msg.content.lower() in ['no', 'nein']:
			await self.player[WITCH].send(translate('witch_no_kill'))
			await self.kill_player()
		else:
			await self.player[WITCH].send(translate('witch_repeat_kill'))
			return
		# witch done, now it is time to kill and start the day

	async def kill_player(self, member):
		"""Kill player from kill list for real."""
		# TODO: Mute player server wide
		# TODO: assign dead-role 
		# TODO: Nick += " (Tod)"
		# TODO: check, if game is over!
		await self.night_to_day(member)

	async def night_to_day(self, member):
		self.current_state = NIGHT_TO_DAY
		# TODO: move all user back to main room (self.day_channel)
		# TODO: inform player who are alive which player died
		await self.voting_village_start()

	async def voting_village_start(self):
		self.current_state = VOTING_VILLAGE
		# TODO: send message in text_channel that it is morning and that voting started
		pass

	async def villager_send_vote(self):
		# TODO: (see wolf_send_vote)
		pass

	async def villager_check_voting_end(self):
		# TODO: (see wolfes_check_voting_end)
		# TODO: check, if all player voted and kill the player with most votes
		# TODO: check, if game is over!
		pass

	def find_player(self, name_or_nick: str):
		"""Find a player by his name or nick. Checks the nick first!"""
		for member in self.player.values():
			if name_or_nick == member.nick:
				return member
		for member in self.player.values():
			if name_or_nick == member.name:
				return member

	def is_wolf(self, member):
		return member in self.player[WOLF]

	def is_witch(self, member):
		return member in self.player[WITCH]

	## handle discord messages
	async def handle_channel_message(self, msg):
		if msg.content == "!start" and self.current_state != PRESTART:
			return await self.start()

	async def handle_message(self, msg):
		state = self.current_state
		if msg.channel == self.text_channel:
			return await self.handle_channel_message(msg)
		elif not self.player:
			return
		elif state == VOTING_WOLF and self.is_wolf(msg.author):
			return await self.wolf_send_vote(msg)
		elif state == VOTING_WITCH_HEAL and self.is_witch(msg.author):
			return await self.witch_awnsered_heal(msg)
		elif state == VOTING_WITCH_KILL and self.is_witch(msg.author):
			return await self.witch_answered_kill(msg)
		# ignore all other messages to this bot
		

game = WerewolfGame(bot)


@bot.event
async def on_ready():
	print(translate('bot_name').format(bot.user.name))
	await game.get_create_all_channel()


@bot.event
async def on_message(msg):
	"""New message received by player."""
	author = msg.author
	content = msg.content

	if author.name != bot.user.name:
		print(f'{author}: {content}')

	game.handle_message(msg)


if __name__ == '__main__':
	load_dotenv()
	bot.run(token=os.getenv('DISCORD_TOKEN'))