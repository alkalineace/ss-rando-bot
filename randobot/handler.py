import asyncio
from datetime import datetime, timedelta, timezone
import isodate
from racetime_bot import RaceHandler, monitor_cmd, can_monitor, msg_actions
import random
from random import SystemRandom
import hashlib
import urllib.request
import string

from randobot.draft import Draft


class RandoHandler(RaceHandler):
    stop_at = ["cancelled", "finished"]

    STANDARD_RACE_PERMALINK = "IQwAACADspoBUgAAAAAAABCK2CA="
    STANDARD_SPOILER_RACE_PERMALINK = "IwUAAAAAwsXwJQAAAAAAgAAAAAA="

    greetings = (
        'I can roll a seed for you, if motivated.',
        'You will get a nice seed. Promised!',
        'It is only a legend that I roll bad seeds. I think.',
        'What is a good seed for you? I need to know. For reasons.',
        'Ghirahim asked me to give you this seed. Is that fine?'
    )

    def __init__(self, website, **kwargs):
        super().__init__(**kwargs)

        self.website = website

        self.loop = asyncio.get_event_loop()
        self.loop_ended = False
        self.random = SystemRandom()
        
    # Called when opening the raceroom - setups a lot of things
    async def begin(self):
        # Reload the presets on room creation
        self.website.reload_presets()

        # Set seed rolling variables
        self.state["version"] = "2.2.0_2b44d20"
        self.state["permalink"] = "gQ3IJkABAAAAAAAA4CCgAREAH8ApAMAb+f/HfgAAwP//AAAAAAAAADAEAAAAAAAAAAAAAPADAAAAAIANUCCCAwAEAAAg/AGIABLIngA="
        self.state["draft"] = None

        # Breaks variables
        self.state["break_set"] = False
        self.state["break_duration"] = 5
        self.state["break_interval"] = 120
        self.state["break_warning_sent"] = False
        self.state["break_in_progress"] = False
        self.state["last_break_time"] = None
        self.state["15_warning_sent"] = False
        self.state["5_warning_sent"] = False
        self.state["1_warning_sent"] = False

        # Spoiler log timer variables
        self.state["sl_timer"] = False
        self.state["sl_timer_duration"] = 42
        self.state["sl_deadline"] = None
        self.state["sl_warnings"] = []
        self.state["sl_timer_expired"] = False

        # First message with buttons to help roll a seed
        if not self.state.get("intro_sent") and not self._race_in_progress():
            await self.send_message(
                'Welcome to Skyward Sword Randomizer! Setup your seed with !permalink <permalink> and !version <version> and roll with !rollseed. ' + random.choice(self.greetings),
                actions=[
                    msg_actions.Action(
                        label='Roll seed',
                        help_text='Create a seed with a specific version and permalink',
                        message='!rollseed ${version} ${preset}',
                        submit='Roll seed',
                        survey=msg_actions.Survey(
                            msg_actions.SelectInput(
                                name='version',
                                label='Version',
                                options=self.website.versions
                            ),
                            msg_actions.SelectInput(
                                name='preset',
                                label='Preset',
                                options=self.website.bit_presets
                            )
                        )
                    ),
                    msg_actions.Action(
                        label='Roll No-BiT seed',
                        help_text='Create a seed where BiT is disabled with a specific version and permalink',
                        message='!rollseed ${version} ${preset}',
                        submit='Roll seed',
                        survey=msg_actions.Survey(
                            msg_actions.SelectInput(
                                name='version',
                                label='Version',
                                options=self.website.versions
                            ),
                            msg_actions.SelectInput(
                                name='preset',
                                label='Preset',
                                options=self.website.nobit_presets
                            )
                        )
                    ),
                    msg_actions.Action(
                        label='Version & Permalink',
                        help_text='List the current version and permalink',
                        message="Version : " + self.state.get("version") + " ; Permalink : " + self.state.get("permalink")
                    )
                ],
                pinned=True
            )
            self.state["intro_sent"] = True

        #await self.edit(hide_comments=True)
        self.loop.create_task(self.handle_scheduled_tasks())

    # Unpin the first message of the room if it has not been unpinned yet on room closing
    async def end(self):
        if self.state.get('pinned_msg'):
            await self.unpin_message(self.state['pinned_msg'])

    # Handles all tasks that use the racetime room timer
    async def handle_scheduled_tasks(self):
        while not self.loop_ended:
            try:
                if self.data.get("started_at") is not None and self.state.get("breaks_set"):
                    break_duration = self.state.get("break_duration")
                    break_interval = self.state.get("break_interval")

                    if self.state.get("last_break_time") is None:
                        self.state["last_break_time"] = isodate.parse_datetime(self.data.get("started_at"))
                    seconds_until_next_break = self._get_seconds_until_next_break()

                    if not self.state.get("break_warning_sent") and seconds_until_next_break < 300:
                        await self.send_message("@entrants Reminder: Next break in 5 minutes.")
                        self.state["break_warning_sent"] = True

                    if not self.state.get("break_in_progress") and seconds_until_next_break < 0:
                        await self.send_message(
                            f"@entrants Break time! Please pause your game for {break_duration} minutes."
                        )
                        self.state["break_in_progress"] = True

                    if self.state.get("break_in_progress") and seconds_until_next_break < break_duration * -60:
                        await self.send_message("@entrants Break ended. You may resume playing.")
                        self.state["break_warning_sent"] = False
                        self.state["break_in_progress"] = False
                        self.state["last_break_time"] = self.state.get("last_break_time") + timedelta(
                            0, 0, 0, 0, break_interval
                        )
                if self.state.get("sl_deadline") is not None and self.state.get("sl_timer"):
                    seconds_left_in_timer = self._get_seconds_left_in_sl_timer()

                    if (30 not in self.state.get("sl_warnings")) and self.state.get("sl_timer_duration") >= 30 and seconds_left_in_timer <= 1800:
                        await self.send_message("@entrants You have 30 minutes left for routing.")
                        self.state["sl_warnings"].append(30)

                    if (20 not in self.state.get("sl_warnings")) and self.state.get("sl_timer_duration") >= 20 and seconds_left_in_timer <= 1200:
                        await self.send_message("@entrants You have 20 minutes left for routing.")
                        self.state["sl_warnings"].append(20)

                    if (10 not in self.state.get("sl_warnings")) and seconds_left_in_timer <= 600:
                        await self.send_message("@entrants You have 10 minutes left for routing.")
                        self.state["sl_warnings"].append(10)
                    
                    if (5 not in self.state.get("sl_warnings")) and seconds_left_in_timer <= 300:
                        await self.send_message("@entrants You have 5 minutes left for routing. Please be ready to start playing soon.")
                        self.state["sl_warnings"].append(5)
                    
                    if (1 not in self.state.get("sl_warnings")) and seconds_left_in_timer <= 60:
                        await self.last_minute_sl_tasks()
                        self.state["sl_warnings"].append(1)
                    
                    if not self.state.get("sl_timer_expired") and seconds_left_in_timer <= 0:
                        self.state["sl_timer_expired"] = True
                        if self._can_force_start_race():
                            await self.send_message(
                                "@entrants Routing time is over, the race will now be force started. Good luck!"
                            )
                            await self.force_start()
                        else:
                            await self.send_message("@entrants Error: Not enough runners were ready to force start the race!")
            except Exception:
                pass
            finally:
                await asyncio.sleep(0.5)

    # Get the id of the first bot message to be able to unpin it later
    async def chat_message(self, data):
        message = data.get('message', {})
        if (
            message.get('is_bot')
            and message.get('bot') == 'SS Rando Bot'
            and message.get('is_pinned')
            and message.get('message_plain', '').startswith('Welcome to Skyward Sword Randomizer!')
        ):
            self.state['pinned_msg'] = message.get('id')
        elif (
            message.get('is_bot')
            and message.get('bot') == 'SS Rando Bot'
            and message.get('is_pinned')
            and message.get('message_plain', '').startswith(self.state["seed_message"])
        ):
            self.state['pinned_msg_seed'] = message.get('id')
        return await super().chat_message(data)
    
    # !breaks
    # Set breaks or disable them
    async def ex_breaks(self, args, message):
        if self._race_in_progress():
            if self.state.get("breaks_set"):
                seconds_until_next_break = self._get_seconds_until_next_break()
                if not self.state.get("break_in_progress"):
                    await self.send_message(
                        f"The next break is in {self._get_formatted_duration_str(seconds_until_next_break)}."
                    )
                else:
                    # During a break, `seconds_until_next_break` = - seconds_since_break_started
                    seconds_until_break_ends = (self.state.get("break_duration") * 60) + seconds_until_next_break
                    await self.send_message(
                        f"The break ends in {self._get_formatted_duration_str(seconds_until_break_ends)}."
                    )
            else:
                await self.send_message("Breaks have not been set.")
        elif len(args) == 0:
            if self.state.get("breaks_set"):
                break_duration = self.state.get("break_duration")
                break_interval = self.state.get("break_interval")
                await self.send_message(f"Breaks are set for {break_duration} minutes every {break_interval} minutes.")
            else:
                await self.send_message(
                    'Breaks are off. Example usage is "!breaks 5 120" for 5-minute breaks every 120 minutes.'
                )
        elif len(args) == 1:
            if args[0] == "off":
                if self.state.get("breaks_set"):
                    self.state["breaks_set"] = False
                    self.state["break_duration"] = 5
                    self.state["break_interval"] = 120
                    await self.send_message("Breaks have been turned off.")
                else:
                    await self.send_message("Breaks are already off.")
            else:
                await self.send_message(
                    'Error parsing command. Example usage is "!breaks 5 120" for 5-minute breaks every 120 minutes.'
                )
        else:
            break_duration, break_interval = args

            try:
                break_duration = max(5, int(break_duration))
            except (TypeError, ValueError):
                await self.send_message(f"{break_duration} is not a valid time.")
                return

            try:
                break_interval = max(60, int(break_interval))
            except (TypeError, ValueError):
                await self.send_message(f"{break_interval} is not a valid time.")
                return

            # Ensure that there's a valid amount of time in-between breaks
            if break_interval <= break_duration + 5:
                await self.send_message("Error. Please ensure there are more than 5 minutes in-between breaks.")
                return

            self.state["breaks_set"] = True
            self.state["break_duration"] = break_duration
            self.state["break_interval"] = break_interval
            await self.send_message(
                f"Breaks have been set for {break_duration} minutes every {break_interval} minutes."
            )

    # !francais
    # Triggers french translation
    async def ex_francais(self, args, message):
        self.state["use_french"] = True
        await self.send_message("Bot responses will now also be in French.")
        await self.send_message(
            "Les réponses du bot seront désormais également en français."
        )

    # !log
    # Sends the spoiler log of the seed in spoiler log races - not currently supported
    # async def ex_log(self, args, message):
        # if self.state.get("spoiler_url") and self.state.get("spoiler"):
        #   url = self.state.get("spoiler_url")
        #   await self.send_message(f"Spoiler Log can be found at {url}")

    # !spoiler
    # Activate a routing timer for spoiler log races.
    async def ex_spoiler(self, args, message):
        if self.state.get("locked") and not can_monitor(message):
            await self.send_message(
                "This command is locked! Only the creator of this room, a race monitor, "
                "or a moderator can set up spoiler log timers."
            )
            if self.state.get("use_french"):
                await self.send_message(
                    "Cette commande est bloquée! Seul le créateur de la salle, un moniteur, "
                    "ou un modérateur peut mettre un minuteur pour spoiler log."
                )
            return

        if self.state.get("permalink_available"):
            await self.send_message("The seed is already rolled! You must run this command before rolling a seed to start a timer.")
            if self.state.get("use_french"):
                await self.send_message(
                    "La seed a déjà été générée! Il faut utiliser cette commande avant de générer une seed pour démarrer un minuteur."
                )
            return
        if len(args) == 0:
            self.state["sl_timer"] = True
            # Default length
            self.state["sl_timer_duration"] = 42
            await self.send_message(f"Will set a {self.state.get('sl_timer_duration')}-minute timer for routing when the seed is rolled.")
            if self.state.get("use_french"):
                await self.send_message(f"Un minuteur de {self.state.get('sl_timer_duration')} minutes pour routage sera mis quand la seed sera générée.")
        elif args[0] == "off":
            self.state["sl_timer"] = False
            await self.send_message("Will NOT set a timer for routing.")
            if self.state.get("use_french"):
                await self.send_message("Il n'y aura PAS un minuteur pour routage.")
        else:
            timer_duration = args[0]

            try:
                timer_duration = max(10, int(timer_duration))
            except (TypeError, ValueError):
                await self.send_message(f"{timer_duration} is not a valid time.")
                return

            self.state["sl_timer"] = True
            self.state["sl_timer_duration"] = timer_duration
            await self.send_message(
                f"Will set a {self.state.get('sl_timer_duration')}-minute timer for routing when the seed is rolled. "
                "Race admin(s), please remember to turn auto-start OFF so all entrants can ready up."
            )
            if self.state.get("use_french"):
                await self.send_message(
                    f"Un minuteur de {self.state.get('sl_timer_duration')} minutes pour routage sera mis quand la seed sera générée."
                    "Les administrateurs de race, désactiver le mode de démarrage automatique afin les participants peuvent se préparer, s'il vous plaît."
                )

    # !info
    # Prints the version and permalink currently set
    # /!\ Might be outdated
    async def ex_info(self, args, message):
        response = ""
        if self.state.get("version") == None:
            response += "No version specified. Using bundled version. "
        else:
            response += f"Version: {self.state.get('version')} "
        response += f"Permalink: {self.state.get('permalink')} "
        if self.state.get("permalink_available"):
            response += "Seed has been rolled. Get it with !permalink. "
            if self.state.get("sl_timer"):
                if (seconds_left := self._get_seconds_left_in_sl_timer()) <= 0:
                    response += "The spoiler log routing timer has expired. "
                else:
                    response += f"The spoiler log routing timer will expire in {self._get_formatted_duration_str(seconds_left)}. "
            else:
                response += "No spoiler log routing timer is set. "
        else:
            response += "Seed not rolled. Roll with !rollseed. "
            if self.state.get("sl_timer"):
                response += f"A {self.state.get('sl_timer_duration')}-minute routing timer will be set when the seed is rolled. "
            else:
                response += "No spoiler log routing timer will be set. "
        await self.send_message(response)

    # !seed
    # Prints info from a seed already rolled
    async def ex_seed(self, args, message):
        if not self.state.get("permalink_available"):
            await self.send_message("There is no seed! Please use !rollseed to get one")
            if self.state.get("use_french"):
                await self.send_message(
                    "Translate 'There is no permalink! Please use !rollseed to get a permalink' to French"
                )
            return
        permalink = self.state.get("permalink")
        hash = self.state.get("hash")
        seed = self.state.get("seed")
        await self.send_message(f"Seed: {seed}, Hash: {hash}, Permalink: {permalink}")
        if self.state.get("use_french"):
            await self.send_message(
                f"Translate 'The permalink is: {permalink}' to French."
            )

    # !lock
    # Locks the raceroom seedrolling
    @monitor_cmd
    async def ex_lock(self, args, message):
        self.state["locked"] = True
        await self.send_message("Seed rolling is now locked.")
        if self.state.get("use_french"):
            await self.send_message(
                "La génération de seed est désormais bloquée."
            )

    # !unlock
    # Unlocks the raceroom seedrolling
    @monitor_cmd
    async def ex_unlock(self, args, message):
        self.state["locked"] = False
        await self.send_message("Seed rolling is now unlocked")
        if self.state.get("use_french"):
            await self.send_message("La génération de seed est désormais débloquée.")

    # !reset
    # Delete any set variable in the raceroom such as the seed, version, permalink, etc...
    @monitor_cmd
    async def ex_reset(self, args, message):
        self.state["permalink"] = self.STANDARD_RACE_PERMALINK
        self.state["seed"] = None
        self.state["hash"] = None
        self.state["permalink_available"] = False
        self.state["sl_timer"] = False
        self.state["sl_timer_duration"] = 42
        self.state["sl_deadline"] = None
        self.state["sl_warnings"] = []
        self.state["sl_timer_expired"] = False
        self.state["spoiler_url"] = None
        self.state["version"] = None
        self.state["draft"] = None
        self.state["break_set"] = False
        self.state["break_duration"] = 5
        self.state["break_interval"] = 120
        self.state["break_warning_sent"] = False
        self.state["break_in_progress"] = False
        self.state["last_break_time"] = None
        self.state["15_warning_sent"] = False
        self.state["5_warning_sent"] = False
        self.state["1_warning_sent"] = False
        self.state["seed_message"] = None
        await self.send_message("The Seed has been reset.")
        if self.state.get("use_french"):
            await self.send_message("La Seed a été réinitialisée")

        if self.state.get('pinned_msg_seed'):
            await self.unpin_message(self.state['pinned_msg_seed'])

        if self.state.get('pinned_msg'):
            await self.pin_message(self.state['pinned_msg'])

    # !permalink
    # Sets the permalink used to roll the seed
    async def ex_permalink(self, args, message):
        permalink = message["message_plain"].split(" ")[1]
        self.state["permalink"] = permalink
        await self.send_message(f"Updated permalink to {permalink}")
        if self.state.get("use_french"):
            await self.send_message(f"Permalien mis à jour: {permalink}")

    # !sgl
    # Sets permalink to SGL settings
    # /!\ Outdated
    async def ex_sgl(self, args, message):
        self.state["permalink"] = "IQ0IIDsD85rpUwAAAAAAACHIFwA="
        await self.send_message(f"Updated the bot to SGL settings")
        if self.state.get("use_french"):
            await self.send_message("Mis à jour le bot pour les paramètres SGL")

    # !coop
    # Sets permalink and version to coop settings
    # /!\ Outdated
    async def ex_coop(self, args, message):
        self.state["permalink"] = "oQ0AIBAD85oJUgAAAAAAAAAQAw=="
        self.state["version"] = "1.2.0_3868e57"
        await self.send_message("Updated the bot to Co-Op S1 settings")
        if self.state.get("use_french"):
            await self.send_message("Mis à jour le bot pour les paramètres Co-Op S1")

    # !s2
    # Sets permalink and version to s2 settings
    # /!\ Outdated
    async def ex_s2(self, args, message):
        self.state["version"] = "1.2.0_f268afa"
        self.state["draft"] = Draft()
        self.state["draft"].set_log_state("off")
        await self.send_message(
            "Updated the bot to Season 2 version. Draft mode has been enabled and reset, and the spoiler log has been disabled. You may now use the command !draftguide (high seed) (low seed) to guide you through the draft process with two players.")
        if self.state.get("use_french"):
            await self.send_message(
                "Mis à jour le bot à la version Saison 2. 'Draft Mode' a été activé et réinitialisé, et le spoiler log a été désactivé. Vous pouvez maintenant utiliser la commande !draftguide (seed haute) (seed basse) pour vous guider durant le processus de sélection avec deux joueurs.")

    # !version
    # Sets version used to roll the seed
    async def ex_version(self, args, message):
        version = message["message_plain"].split(" ")[1]
        if version[0] == 'v':
            version = version[1:]
        self.state["version"] = version
        await self.send_message(f"Version set to {version}")
        if self.state.get("use_french"):
            await self.send_message(f"Version définie à {version}")

    # !draft
    # Enable draft mode
    # /!\ Needs update
    async def ex_draft(self, args, message):
        if self.state["draft"] is not None:
            await self.send_message("Draft mode is already active")
            if self.state.get("use_french"):
                await self.send_message("'Draft Mode' est déjà actif")
        else:
            self.state["draft"] = Draft()
            await self.send_message(
                "Draft mode activated. The !ban and !pick commands are now active"
            )
            if self.state.get("use_french"):
                await self.send_message(
                    "'Draft Mode' activé. Les commandes !ban et !pick sont désormais utilisables"
                )

    # !draftoff
    # Disable draft mode
    async def ex_draftoff(self, args, message):
        self.state["draft"] = None
        await self.send_message("Draft mode deactivated")
        if self.state.get("use_french"):
            await self.send_message("'Draft Mode' désactivé")

    # !ban
    # Ban a setting if in Draft mode
    async def ex_ban(self, args, message):
        if self.state["draft"] is None:
            await self.send_message("Draft mode is not active")
            if self.state.get("use_french"):
                await self.send_message("Draft Mode' n'est pas actif")
        else:
            if len(args) == 0:
                await self.send_message("No mode specified")
                if self.state.get("use_french"):
                    await self.send_message("Aucun mode spécifié")
            else:
                await self.send_message(self.state["draft"].ban(" ".join(args)))

    # !pick
    # Pick a setting if in Draft mode
    async def ex_pick(self, args, message):
        if self.state["draft"] is None:
            await self.send_message("Draft mode is not active")
            if self.state.get("use_french"):
                await self.send_message("'Draft Mode' n'est pas actif")
        else:
            if len(args) == 0:
                await self.send_message("No mode specified")
                if self.state.get("use_french"):
                    await self.send_message("Aucun mode spécifié")
            else:
                await self.send_message(self.state["draft"].pick(" ".join(args)))

    # !draftlog
    # Enables or disables Spoiler log for Draft races
    async def ex_draftlog(self, args, message):
        if self.state["draft"] is None:
            await self.send_message("Draft mode is not active")
            if self.state.get("use_french"):
                await self.send_message("'Draft Mode' n'est pas actif")
        else:
            if len(args) == 0:
                await self.send_message(
                    "Please specify 'off' or 'on' to deactivate or activate the randomizer's spoiler log generation."
                )
                if self.state.get("use_french"):
                    await self.send_message(
                        "Veuillez spécifier 'off' ou 'on' pour désactiver ou activer la génération du Spoier Log"
                    )
            else:
                await self.send_message(
                    self.state["draft"].set_log_state("".join(args).strip())
                )

    # !draftguide
    # Sets the 2 players that will be drafting : Higher seed, then Lower seed
    async def ex_draftguide(self, args, message):
        if self.state["draft"] is None:
            await self.send_message("Draft mode is not active")
            if self.state.get("use_french"):
                await self.send_message("'Draft Mode' n'est pas actif")
        else:
            if len(args) != 2:
                await self.send_message(
                    "Please specify the higher seed and lower seed player names (in 1 word each) respectively for the guide process."
                )
                if self.state.get("use_french"):
                    await self.send_message(
                        "Veuillez spécifier les noms de la seed la plus haute et plus basse (en 1 mot chacun) pour le guidage."
                    )
            else:
                self.state["draft"].banned = []
                self.state["draft"].picked = []
                await self.send_message(
                    self.state["draft"].seeding_init(args[0], args[1])
                )

    # !draftguideoff
    # Deactivate Draft guide mode
    async def ex_draftguideoff(self, args, message):
        if self.state["draft"] is None:
            await self.send_message("Draft mode is not active")
            if self.state.get("use_french"):
                await self.send_message("'Draft Mode' n'est pas actif")
        self.state["draft"].guide_step = None
        await self.send_message("Draft guide mode deactivated.")
        if self.state.get("use_french"):
            await self.send_message("Guide du 'Draft Mode' désactivé")

    # !draftstatus
    # Prints the banned and selected settings, as well as the next action needed
    async def ex_draftstatus(self, args, message):
        draft = self.state["draft"]
        if draft is None:
            await self.send_message("Draft mode is not active")
            if self.state.get("use_french"):
                await self.send_message("'Draft Mode' n'est pas actif")
        else:
            status_message = f"Draft mode is active. Currently banned: {draft.banned}. Currently picked: {draft.picked}. Spoiler log: {draft.spoiler_log}."
            if self.state["draft"].guide_step is not None:
                if self.state["draft"].guide_step in [0, 3]:
                    status_message += f" Next step: {self.state['draft'].low_seed}"
                else:
                    status_message += f" Next step: {self.state['draft'].high_seed}"
                if self.state["draft"].guide_step % 2 == 0:
                    status_message += f" bans."
                else:
                    status_message += f" picks."
            await self.send_message(status_message)

    # !draftoptions
    # Prints the available options for Draft
    async def ex_draftoptions(self, args, message):
        if self.state["draft"] is None:
            await self.send_message("Draft mode is not active")
            if self.state.get("use_french"):
                await self.send_message("'Draft Mode' n'est pas actif")
        else:
            await self.send_message(
                f"Draft options: {', '.join(self.state['draft'].OPTIONS.keys())}"
            )

    # !rollseed
    # Rolls a seed
    async def ex_rollseed(self, args, message):
        print("rolling seed")
        if self.state.get("locked") and not can_monitor(message):
            await self.send_message(
                "Seed rolling is locked! Only the creator of this room, a race monitor, "
                "or a moderator can roll a seed."
            )
            if self.state.get("use_french"):
                await self.send_message(
                    "La génération de seed est bloquée! Seul le créateur de la salle, un moniteur, "
                    "ou un modérateur peut générer une seed."
                )

            return

        if self.state.get("permalink_available"):
            await self.send_message("The seed is already rolled! Use !seed to view it.")
            if self.state.get("use_french"):
                await self.send_message(
                    "La seed a déjà été générée! Utilisez !seed pour la voir."
                )
            return

        await self.send_message("Rolling seed.....")
        if self.state["draft"] is not None:
            (mode, perma) = self.state["draft"].make_selection()
            await self.send_message(f"Selected mode {mode}")
            self.state["permalink"] = perma
        
        if len(args) > 1:
            self.state["version"] = message["message_plain"].split(" ")[1]
        version = self.state.get("version") or "2.2.0_2b44d20"
        commit = version.split('_')[1]
        seed_start = self.random.choice('123456789')
        seed_end = "".join(self.random.choice(string.digits) for _ in range(17))
        seed_name = seed_start + seed_end
        if len(args) > 1:
            self.state["permalink"] = message["message_plain"].split(" ")[2]
        permalink = f"{self.state.get('permalink')}#{seed_name}"
        current_hash = hashlib.md5()
        current_hash.update(str(seed_name).encode("ASCII"))
        current_hash.update(permalink.encode("ASCII"))
        current_hash.update(version.encode("ASCII"))
        with urllib.request.urlopen(
                f"http://raw.githubusercontent.com/ssrando/ssrando/{commit}/names.txt"
        ) as f:
            data = f.read().decode("utf-8")
            names = [s.strip() for s in data.split("\n")]
        hash_random = random.Random()
        hash_random.seed(current_hash.digest())
        hash = " ".join(hash_random.choice(names) for _ in range(3))
        seed = seed_name

        self.logger.info(permalink)

        if self.state.get('pinned_msg'):
            await self.unpin_message(self.state['pinned_msg'])

        self.state["permalink"] = permalink
        self.state["hash"] = hash
        self.state["seed"] = seed
        self.state["permalink_available"] = True

        self.state["seed_message"] = f"{version} Permalink: {permalink}, Hash: {hash}"

        if self.state.get("sl_timer"):
            self.state["sl_deadline"] = datetime.now(timezone.utc) + timedelta(0,self.state.get('sl_timer_duration') * 60)
            self.state["seed_message"] += f", Force start at {self.state.get('sl_deadline').strftime('%H:%M:%S')} UTC"

        await self.send_message(self.state.get("seed_message"), pinned=True)

        if self.state.get("sl_timer"):
            self.state["seed_roll_time"] = datetime.now(timezone.utc)
            await self.send_message(
                f"A {self.state.get('sl_timer_duration')}-minute timer has been set. "
                "Please ready up before the timer expires, as the race will be force started when the timer expires "
                f"(at {self.state.get('sl_deadline').strftime('%H:%M:%S')} UTC)."
            )

        #     url = generated_seed.get("spoiler_log_url")
        #     self.state["spoiler_url"] = url
        #     await self.send_message(f"Spoiler Log URL available at {url}")
        #     if self.state.get("use_french"):
        #         await self.send_message(f"Spoiler Log disponible à l'url: {url}")

        if self.state["draft"] is not None:
            await self.set_raceinfo(
                f" - {version} Draft Option: {mode}, Seed: {seed}, Hash: {hash}, Permalink: {permalink}",
                False,
                False,
            )
        else:
            await self.set_raceinfo(
                f" - {version} Seed: {seed}, Hash: {hash}, Permalink: {permalink}",
                False,
                False,
            )
    
    async def last_minute_sl_tasks(self):
        filename_start = self.random.choice('123456789')
        filename_end = "".join(self.random.choice(string.digits) for _ in range(5))
        filename = filename_start + filename_end
        await self.send_message(f"@entrants The race will start in one minute. Please use the filename '{filename}'. ")
        for entrant in self.data.get("entrants"):
            if (entrant.get("status").get("value") == "not_ready"):
                await self.send_message(f"@{entrant.get('user').get('name')}, please ready up!")
        

    # Returns True is race is ongoing
    def _race_in_progress(self):
        return self.data.get("status").get("value") in ("pending", "in_progress")

    # Returns time until next break in seconds
    def _get_seconds_until_next_break(self):
        if self.state.get("last_break_time") is None:
            return 0

        seconds_since_last_break = (datetime.now(timezone.utc) - self.state.get("last_break_time")).total_seconds()
        return (self.state.get("break_interval") * 60) - seconds_since_last_break
    
    # Returns time left in the timer before race start in spoiler log races
    def _get_seconds_left_in_sl_timer(self):
        if not self.state.get("permalink_available"):
            return 0

        return (self.state.get("sl_deadline") - datetime.now(timezone.utc)).total_seconds()
    
    def _get_formatted_duration_str(self, duration_in_seconds):
        if duration_in_seconds < 0:
            return "Invalid time"
        if duration_in_seconds == 0:
            return "0 seconds"

        hours = duration_in_seconds // 3600
        minutes = (duration_in_seconds - (hours * 3600)) // 60
        seconds = duration_in_seconds - (hours * 3600) - (minutes * 60)

        formatted_str = []
        if hours != 0:
            hours_string = f"{int(hours)} hour"
            if hours > 1:
                hours_string += "s"
            formatted_str.append(hours_string)
        if minutes != 0:
            minutes_string = f"{int(minutes)} minute"
            if minutes > 1:
                minutes_string += "s"
            formatted_str.append(minutes_string)
        if seconds != 0:
            seconds_string = f"{int(seconds)} second"
            if seconds > 1:
                seconds_string += "s"
            formatted_str.append(seconds_string)

        if len(formatted_str) == 3:
            formatted_str[2] = f"and {formatted_str[2]}"
            return ", ".join(formatted_str)
        elif len(formatted_str) == 2:
            return f"{formatted_str[0]} and {formatted_str[1]}"
        else:
            return formatted_str[0]
    
    def _can_force_start_race(self):
        num_ready = 0
        for entrant in self.data.get("entrants"):
            if (entrant.get("status").get("value") == "ready"):
                num_ready += 1
        # cannot force start a race with less than 2 entrants ready.
        return num_ready >= 2
