# GUIDE: Creating SLSB Patches for SLAL Animation Packs

This guide assumes you have the [SLSB.Convert.Dev.Essentials](https://discord.com/channels/906462751101177886/1177559131591291010) archive from Scrab's Discord and have its content extracted out to a directory with a short and whitespaces-free full path, such as "D:/SkyrimMods/SLSB.Convert.Dev.Essentials".

The following steps will help you finalize the dev evironment required to convert SLAL (SexLab Animation Loader) animation packs into SLSB (SexLab Scene Builder) format.

## **Step 1: Grab the Requisite Dev-Tools:**
   1. Grab and intall [Python 3.10+](https://www.python.org/downloads/)
   2. Grab [FNIS Behavior SE 7.6 XXL](https://www.nexusmods.com/skyrimspecialedition/mods/3038?tab=files&file_id=124620)
   3. Grab [FNIS Creature Pack SE 7.6](https://www.nexusmods.com/skyrimspecialedition/mods/3038?tab=files&file_id=124621)
   4. Grab [Command Line FNIS for Modders](https://www.nexusmods.com/skyrim/mods/81882?tab=files&file_id=1000235248)
   5. Grab [SexLab AnimStageLabels](https://www.loverslab.com/files/file/27407-sexlab-anim-stage-labels/?do=download&r=2059949)
   6. Grab [HentaiRim Tags](https://www.loverslab.com/files/file/43761-hentairim-p/?do=download&r=2119047)

## **Step 2: Incoporate the Downloaded Dev-Tools:**
   1. Ensure that Python is accessible from the command line (test by typing "python3" in a terminal window).
   2. From the **FNIS Behavior SE 7.6 XXL** archive, extract the **"tools"** folder in "FNIS Behavior SE 7.6 XXL\Data" to **[dev_env]\base_game_replica\Data**.
   3. From the **FNIS Creature Pack SE 7.6** archive, extract the **"tools"** folder in "FNIS Creature Pack SE 7.6\Data" to **[dev_env]\base_game_replica\Data**.
   4. From the **Command Line FNIS for Modders** archive, extract the **"tools"** folder to **[dev_env]\base_game_replica\Data**.
   5. From the **SexLab AnimStageLabels** archive, extract the contents of the **"SLATE"** folder in "SLAnimStageLabels\SKSE\Plugins" to **[dev_env]\slate_action_logs**.
   6. From the **HentaiRim Tags** archive, extract the contents of the **"SLATE"** folder to **[dev_env]\slate_action_logs**.

## **Step 3: Update SLSB Jsons to Maintain Hashes:**
SLSB and SLPP rely on hashes to identify scenes or stages. These hashes are randomly generated upon export, which can cause users to lose animation toggles (enable/disable) as well as custom allignment adjustments and inserted annotations upon successive update. To avoid this, update the hashes source by doing the following before each update:

   1. Extract the latest `Automated.SLSB.Conversions.v_.7z`.
   2. Search for `json` in the extracted directory.
   3. Copy all JSON files to the directory `[dev_env]\updated_slsb_jsons`.

## **Step 4: Converting SLAL Packs to SLSB Format:**
   1. Extract your SLAL pack(s) and place them in the directory titled `SLAL_Packs`.
   2. **VERY IMP:** Ensure the path is structured like this ==> **./SLALPacks/BillyyCreatures/SLAnims/json** (see example dir structures inside 'SLAL_Packs' if confused).
   3. Launch **execute_convert_full.cmd** and wait for the conversion process to complete.
   4. Grab the converted SLSB patch from **SLSB_Outputs** and install this on top of the patched SLAL pack.
   5. Profit.