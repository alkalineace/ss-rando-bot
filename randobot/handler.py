import asyncio
from datetime import datetime, timedelta
from racetime_bot import RaceHandler, monitor_cmd, can_monitor
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.loop = asyncio.get_event_loop()
        self.loop_ended = False
        self.random = SystemRandom()

    async def begin(self):
        if not self.state.get("intro_sent") and not self._race_in_progress():
            await self.send_message(
                "Welcome to Skyward Sword Randomizer! Setup your seed with !permalink <permalink> and !version <version> and roll with !rollseed"
            )
            await self.send_message(
                "If no permalink is specified, standard race settings will be used. "
                "If no version is specified, the version bundled with the bot will be used. Ask a member of server staff for details on which version this is"
            )
            await self.send_message(
                "To enable draft mode, use !draft. Currently, draft mode must be self moderated, and is only designed for use in 1v1 races. If no picks or bans "
                "are specified, a random option will be selected from the list of possible options"
            )
            self.state["intro_sent"] = True
        self.state["permalink"] = self.STANDARD_RACE_PERMALINK
        self.state["spoiler"] = False
        self.state["version"] = None
        self.state["draft"] = None
        #await self.edit(hide_comments=True)

    async def ex_francais(self, args, message):
        self.state["use_french"] = True
        await self.send_message("Bot responses will now also be in French.")
        await self.send_message(
            "Les réponses du bot seront désormais également en français."
        )

    async def ex_log(self, args, message):
        if self.state.get("spoiler_url") and self.state.get("spoiler"):
            url = self.state.get("spoiler_url")
            await self.send_message(f"Spoiler Log can be found at {url}")

    async def ex_spoiler(self, args, message):
        spoiler = not self.state.get("spoiler")
        self.state["spoiler"] = spoiler
        if spoiler:
            await self.send_message("Will create a public sharable Spoiler Log")
            if self.state.get("use_french"):
                await self.send_message("Un Spoiler Log public et partageable sera créé")
        else:
            await self.send_message("Will NOT create a public sharable Spoiler Log")
            if self.state.get("use_french"):
                await self.send_message("Un Spoiler Log public et partageable ne sera PAS crée")

    async def ex_info(self, args, message):
        response = ""
        if self.state.get("version") == None:
            response += "No version specified. Using bundled version. "
        else:
            response += f"Version: {self.state.get('version')} "
        response += f"Permalink: {self.state.get('permalink')} "
        if self.state.get("spoiler"):
            response += "Spoiler log will be generated and a link will be provided. "
        else:
            response += "Spoiler log will not be generated. "
        if self.state.get("peramlink_available"):
            response += "Seed has been rolled. Get it with !permalink. "
        else:
            response += "Seed not rolled. Roll with !rollseed. "
        await self.send_message(response)

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

    @monitor_cmd
    async def ex_lock(self, args, message):
        self.state["locked"] = True
        await self.send_message("Seed rolling is now locked.")
        if self.state.get("use_french"):
            await self.send_message(
                "La génération de seed est désormais bloquée."
            )

    @monitor_cmd
    async def ex_unlock(self, args, message):
        self.state["locked"] = False
        await self.send_message("Seed rolling is now unlocked")
        if self.state.get("use_french"):
            await self.send_message("La génération de seed est désormais débloquée.")

    @monitor_cmd
    async def ex_reset(self, args, message):
        self.state["permalink"] = self.STANDARD_RACE_PERMALINK
        self.state["seed"] = None
        self.state["hash"] = None
        self.state["permalink_available"] = False
        self.state["spoiler"] = False
        self.state["spoiler_url"] = None
        self.state["version"] = None
        self.state["draft"] = None
        await self.send_message("The Seed has been reset.")
        if self.state.get("use_french"):
            await self.send_message("La Seed a été réinitialisée")

    async def ex_permalink(self, args, message):
        permalink = args[0]
        self.state["permalink"] = permalink
        await self.send_message(f"Updated permalink to {permalink}")
        if self.state.get("use_french"):
            await self.send_message(f"Permalien mis à jour: {permalink}")

    async def ex_sgl(self, args, message):
        self.state["permalink"] = "IQ0IIDsD85rpUwAAAAAAACHIFwA="
        await self.send_message(f"Updated the bot to SGL settings")
        if self.state.get("use_french"):
            await self.send_message("Mis à jour le bot pour les paramètres SGL")

    async def ex_coop(self, args, message):
        self.state["permalink"] = "oQ0AIBAD85oJUgAAAAAAAAAQAw=="
        self.state["version"] = "1.2.0_3868e57"
        await self.send_message("Updated the bot to Co-Op S1 settings")
        if self.state.get("use_french"):
            await self.send_message("Mis à jour le bot pour les paramètres Co-Op S1")

    async def ex_s2(self, args, message):
        self.state["version"] = "1.2.0_f268afa"
        self.state["draft"] = Draft()
        self.state["draft"].set_log_state("off")
        await self.send_message(
            "Updated the bot to Season 2 version. Draft mode has been enabled and reset, and the spoiler log has been disabled. You may now use the command !draftguide (high seed) (low seed) to guide you through the draft process with two players.")
        if self.state.get("use_french"):
            await self.send_message(
                "Mis à jour le bot à la version Saison 2. 'Draft Mode' a été activé et réinitialisé, et le spoiler log a été désactivé. Vous pouvez maintenant utiliser la commande !draftguide (seed haute) (seed basse) pour vous guider durant le processus de sélection avec deux joueurs.")

    async def ex_version(self, args, message):
        version = args[0]
        if version[0] == 'v':
            version = version[1:]
        self.state["version"] = version
        await self.send_message(f"Version set to {version}")
        if self.state.get("use_french"):
            await self.send_message(f"Version définie à {version}")

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

    async def ex_draftoff(self, args, message):
        self.state["draft"] = None
        await self.send_message("Draft mode deactivated")
        if self.state.get("use_french"):
            await self.send_message("'Draft Mode' désactivé")

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

    async def ex_draftguideoff(self, args, message):
        if self.state["draft"] is None:
            await self.send_message("Draft mode is not active")
            if self.state.get("use_french"):
                await self.send_message("'Draft Mode' n'est pas actif")
        self.state["draft"].guide_step = None
        await self.send_message("Draft guide mode deactivated.")
        if self.state.get("use_french"):
            await self.send_message("Guide du 'Draft Mode' désactivé")

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

    async def ex_draftoptions(self, args, message):
        if self.state["draft"] is None:
            await self.send_message("Draft mode is not active")
            if self.state.get("use_french"):
                await self.send_message("'Draft Mode' n'est pas actif")
        else:
            await self.send_message(
                f"Draft options: {', '.join(self.state['draft'].OPTIONS.keys())}"
            )

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
        version = self.state.get("version") or "2.0.0_b9f6c8"
        commit = version.split('_')[1]
        seed_start = self.random.choice('123456789')
        seed_end = "".join(self.random.choice(string.digits) for _ in range(17))
        seed_name = seed_start + seed_end
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

        self.state["permalink"] = permalink
        self.state["hash"] = hash
        self.state["seed"] = seed
        self.state["permalink_available"] = True

        await self.send_message(f"{version} Permalink: {permalink}, Hash: {hash}")

        if self.state.get("spoiler"):
            url = generated_seed.get("spoiler_log_url")
            self.state["spoiler_url"] = url
            await self.send_message(f"Spoiler Log URL available at {url}")
            if self.state.get("use_french"):
                await self.send_message(f"Spoiler Log disponible à l'url: {url}")

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

    def _race_in_progress(self):
        return self.data.get("status").get("value") in ("pending", "in_progress")